#-*- coding: utf-8 -*-
'''
CoassignViewer
    : Automatic building & launching & reporting system for a large number of coding assignment files.

Requirements:
    python 2.x
    cmake
    Pygments (install via pip install pygments)
    Unidecode (install via pip install unidecode)

Tested language & platform:
    C - Microsoft Visual Studio 2010 on Windows 10 (Kor)
    C - Microsoft Visual C++ 2010 Express on Windows 8.1 with Bing (Eng)

* On MS Windows, please add following paths to the system path. XX.X means your Visual Studio version.
    C:\Program Files (x86)\Microsoft Visual Studio XX.X\VC\bin
    C:\Program Files (x86)\Microsoft Visual Studio XX.X\Common7\IDE


usage: coassign-viewer.py [-h] [--user-input USER_INPUT]
                          [--file-layout FILE_LAYOUT] [--timeout TIMEOUT]
                          [--run-only RUN_ONLY]
                          [--assignment-alias ASSIGNMENT_ALIAS]
                          [--output-dir OUTPUT_DIR]
                          assignment_dir

Automatic building & launching & reporting system for a large number of coding assignment files.

positional arguments:
  assignment_dir        a direcory that has source files. avoid including
                        hangul characters in its full path.

optional arguments:
  -h, --help            show this help message and exit
  --user-input USER_INPUT
                        specify USER_INPUT to be sent to the stdin of the
                        target programs.
                        default is an empty string.
  --file-layout FILE_LAYOUT
                        indicates file layout in the assignment_dir.
                        default: 0
                        0 - one source file per each student.
                        1 - one zip file for each student. the zip file has
                        multiple source files and each source file represents
                        each program.
  --timeout TIMEOUT     each target program is killed when TIMEOUT(seconds)
                        is reached. useful for infinite loop cases.
                        default: 2.0
  --run-only RUN_ONLY   when specified, run each target program without build.
                        you may use it when you want change USER_INPUT without
                        build. if the programming language of the source file
                        does not require build process, CoassignViewer
                        automatically skips the build process without
                        specifying this option.
  --assignment-alias ASSIGNMENT_ALIAS
                        specify ASSIGNMENT_ALIAS for each assignment_dir.
                        ASSIGNMENT_ALIAS is used when making a sub-directory
                        in OUTPUT_DIR and the final report file.
                        default: "basename" of assignment_dir (bar if
                        assignment_dir is /foo/bar/).
  --output-dir OUTPUT_DIR
                        specify OUTPUT_DIR in which the final report file
                        and build output files to be generated.
                        default: ./output
'''

import os, sys, shutil, subprocess, threading, time, argparse, zipfile
from pygments import highlight
from pygments.lexers import guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from unidecode import unidecode

reload(sys)
sys.setdefaultencoding('cp949')

############################################
# functions for preparation

def unzipInAssignDir(assignDir):
    zipFileNames = []
    for name in os.listdir(assignDir):
        filePath = opjoin(assignDir, name)
        if zipfile.is_zipfile(filePath):
            with zipfile.ZipFile(filePath, 'r') as z:
                unzipDir = os.path.splitext(filePath)[0]
                z.extractall(unzipDir)
                zipFileNames.append(name)
    return zipFileNames

def removeUnzipDirsInAssignDir(assignDir, unzipDirNames):
    for d in unzipDirNames:
        shutil.rmtree(opjoin(assignDir, d))

def copyAndDecodeAssignDirToOutDirRecursive(assignDir, outputDir, assignAlias, decode2orig):
    decodeAlias = unidecode(unicode(assignAlias))
    decode2orig[decodeAlias] = assignAlias
    srcDir = assignDir
    destDir = opjoin(outputDir, decodeAlias)

    if os.path.exists(destDir):
        shutil.rmtree(destDir)
        time.sleep(.01)
    shutil.copytree(assignDir, destDir)

    for root, dirs, files in os.walk(destDir, topdown=False):
        for name in dirs:
            # decode2orig['\hagsaeng01\munje2'] == '\학생01\문제2'
            pathAfterDestDir = opjoin(root, name)
            pathAfterDestDir = pathAfterDestDir.replace(destDir, '')
            decode2orig[unidecode(unicode(pathAfterDestDir))] = pathAfterDestDir

            # decode2orig['hagsaeng01'] == '학생01'
            decodeName = unidecode(unicode(name))
            decode2orig[decodeName] = name
            os.rename(opjoin(root, name), opjoin(root, decodeName))

        for name in files:
            # decode2orig['\hagsaeng01\munje2.c'] == '\학생01\문제2.c'
            pathAfterDestDir = opjoin(root, name)
            pathAfterDestDir = pathAfterDestDir.replace(destDir, '')
            decode2orig[unidecode(unicode(pathAfterDestDir))] = pathAfterDestDir

            # decode2orig['munje2.c'] == '문제2.c'
            decodeName = unidecode(unicode(name))
            os.rename(opjoin(root, name), opjoin(root, decodeName))
            decode2orig[decodeName] = name
            decode2orig[os.path.splitext(decodeName)[0]] = os.path.splitext(name)[0]

    return destDir

def removeZipFileInDestDir(destDir, zipFileNames):
    for name in zipFileNames:
        os.remove(opjoin(destDir, unidecode(unicode(name))))

def makeLeafDirAndMoveFile(destDir):
    for root, dirs, files in os.walk(destDir, topdown=False):
        for fileName in files:
            dirName = os.path.splitext(fileName)[0]
            dirPath = opjoin(root, dirName)
            os.mkdir(dirPath)
            os.rename(opjoin(root, fileName), opjoin(dirPath, fileName))


def preProcess():
    decode2orig = {}

    zipFileNames = unzipInAssignDir(gArgs.assignment_dir[0])
    unzipDirNames = [os.path.splitext(zipFileName)[0] for zipFileName in zipFileNames]
    destDir = copyAndDecodeAssignDirToOutDirRecursive(gArgs.assignment_dir[0], gArgs.output_dir, gArgs.assignment_alias, decode2orig)
    removeZipFileInDestDir(destDir, zipFileNames)

    if gArgs.file_layout==0:
        makeLeafDirAndMoveFile(destDir)

    return destDir, decode2orig, unzipDirNames

def postProcess(unzipDirNames):
    removeUnzipDirsInAssignDir(gArgs.assignment_dir[0], unzipDirNames)

############################################
# main functions

# # return workDir
# def prepare_old(origFilePath, outputDir, alias, projName, fileName):
    # # make workspace directory for projName
    # workDir = opjoin(outputDir, opjoin(alias, projName))
    # try:
        # os.makedirs(workDir)
    # except OSError as e:
        # pass

    # # copy assignment file to build directory
    # shutil.copy(origFilePath, workDir)

    # return workDir

# return CMakeLists.txt code
def getCMakeListsFileContents(projName, srcFileNames):
    srcFileCount = 0
    code = ''
    code += 'cmake_minimum_required(VERSION 2.6)\n'
    code += 'project(%s)\n'%projName
    code += 'add_executable(%s '%projName
    for fileName in srcFileNames:
        ext = os.path.splitext(fileName)[1].lower()
        if ext=='.c' or ext=='.cpp':
            code += '%s '%fileName
            srcFileCount += 1
    code += ')\n'
    return code

# return errorCode, buildLog
def build(repSrcExt, buildDir, projName, srcFileNames):

    if repSrcExt in codeExt:
        return codeExt[repSrcExt]['build-func'](buildDir, projName, srcFileNames)
    else:
        print '%s%s is not a supported source file type.'%(logPrefix, repSrcExt)
        return None, None 

def onTimeOut(proc):
    gKillFunc(proc)

# return exitType, output(stdout) of target program
# exitType:
#   0 - normal exit
#   1 - forced kill due to timeout
def run(repSrcExt, workDir, projName, userInput, timeOut):
    proc = subprocess.Popen([gRunPrefix + codeExt[repSrcExt]['runcmd-func'](projName)], cwd=workDir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    timer = threading.Timer(timeOut, onTimeOut, [proc])
    
    timer.start()
    stdoutStr = proc.communicate(userInput)[0]

    if timer.is_alive():
        timer.cancel()
        return 0, stdoutStr
    else:
        return 1, stdoutStr

############################################
# functions for report
def generateReport(args, submittedFileNames, srcFileLists, buildRetCodes, buildLogs, exitTypes, stdoutStrs):
    htmlCode = ''

    # header
    htmlCode += '''<html>
<head>
<title>Assignment %s Report</title>
<style type="text/css">
%s
</style>
</head>
<body>'''%(args.assignment_alias, HtmlFormatter().get_style_defs())

    # beginning
    htmlCode += '''<pre>
    Assignment %s Report

    Assignment directory: %s
    Output directory: %s
    User input: %s
    File layout: %d
    Timeout: %f
    Run only: %d
</pre>'''%(args.assignment_alias, os.path.abspath(args.assignment_dir[0]), opjoin(os.path.abspath(args.output_dir), unidecode(unicode(args.assignment_alias))), 
        args.user_input, args.file_layout, args.timeout, args.run_only)

    # main table
    htmlCode += '''<table border=1>
<tr>
<td>Submission Name</td>
<td>Source Files</td>
<td>Output</td>
<td>Score</td>
<td>Comment</td>
</tr>'''

    for i in range(len(submittedFileNames)):
        htmlCode += '<tr>\n'
        htmlCode += '<td>%s</td>\n'%submittedFileNames[i]
        htmlCode += '<td>%s</td>\n'%getSourcesTable(srcFileLists[i])
        htmlCode += '<td>%s</td>\n'%getOutput(buildRetCodes[i], buildLogs[i], exitTypes[i], stdoutStrs[i])
        htmlCode += '<td>%s</td>\n'%''
        htmlCode += '<td>%s</td>\n'%''
        htmlCode += '</tr>\n'

    htmlCode += '</table>\n'

    # footer
    htmlCode += '''</body>
</html>'''

    # write html
    with open(opjoin(opjoin(args.output_dir, unidecode(unicode(args.assignment_alias))),'report-%s.html'%args.assignment_alias), 'w') as f:
        f.write(htmlCode.encode('utf-8'))
        # try:
            # f.write(htmlCode)
        # except UnicodeEncodeError:
            # f.write(htmlCode.encode('utf-8'))
        
def getSourcesTable(srcPaths):
    htmlCode = ''
    for srcPath in srcPaths:
        htmlCode += '%s\n'%os.path.basename(srcPath)
        htmlCode += '%s\n'%getRenderedSource(srcPath)
    return htmlCode 

def getRenderedSource(srcPath):
    with open(srcPath, 'r') as f:
        sourceCode = f.read()
    return highlight(sourceCode, guess_lexer_for_filename(srcPath, sourceCode), HtmlFormatter())

def getOutput(buildRetCode, buildLog, exitType, stdoutStr):
    s = '<pre>\n'
    if buildRetCode!=0: # build error
        s += buildLog
    else:
        if exitType == 1:   # time out
            s += 'Timeout'
        else:
            s += stdoutStr
    return s
 
############################################
# functions for each source file extension

# return errorCode, buildLog
def build_c_cpp(buildDir, projName, srcFileNames):
    # make CMakeLists.txt
    cmakeCode = getCMakeListsFileContents(projName, srcFileNames)
    with open(opjoin(buildDir,'CMakeLists.txt'), 'w') as f:
        f.write(cmakeCode)

    # build
    try:
        buildLog = subprocess.check_output('cd %s && %s'%(buildDir, gBuildCmd), shell=True)
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output
    else:
        return 0, buildLog

def runcmd_c_cpp(projName):
    return '%s.exe'%projName

############################################
# functions for each platform

def kill_windows(proc):
    # http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
    subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=proc.pid))

def kill_linux(proc):
    # http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
    proc.kill()


############################################
# pre-defined

env = {'nt':{}, 'posix':{}}
env['nt']['build-cmd'] = 'vcvars32.bat && cmake ./ -G "NMake Makefiles" && nmake'
env['nt']['kill-func'] = kill_windows
env['nt']['run-prefix'] = ''
env['posix']['build-cmd'] = 'cmake ./; make'
env['posix']['kill-func'] = kill_linux
env['posix']['run-prefix'] = 'exec '

gBuildCmd = env[os.name]['build-cmd']
gKillFunc = env[os.name]['kill-func']
gRunPrefix = env[os.name]['run-prefix']

codeExt = {'.c':{}, '.cpp':{}}
codeExt['.c']['build-func'] = build_c_cpp
codeExt['.c']['runcmd-func'] = runcmd_c_cpp
codeExt['.cpp']['build-func'] = build_c_cpp
codeExt['.cpp']['runcmd-func'] = runcmd_c_cpp

opjoin = os.path.join
logPrefix = '# '

############################################
# main routine

parser = argparse.ArgumentParser(prog='coassign-viewer.py', description='Automatic building & launching & reporting system for a large number of coding assignment files.', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('assignment_dir', nargs=1,
                    help='a direcory that has submitted files. ')
parser.add_argument('--user-input', default='',
                    help='specify USER_INPUT to be sent to the stdin of the \ntarget programs. \ndefault is an empty string.')
parser.add_argument('--file-layout', default=0, type=int,
                    help='''indicates file layout in the assignment_dir. \ndefault: 0
0 - one source file per each student.
1 - one zip file for each student. the zip file has \nmultiple source files and each source file represents \neach program.''')
parser.add_argument('--timeout', default=2., type=float,
                    help='each target program is killed when TIMEOUT(seconds) \nis reached. useful for infinite loop cases. \ndefault: 2.0')
parser.add_argument('--run-only',
                    help='''when specified, run each target program without build. \nyou may use it when you want change USER_INPUT without
build. if the programming language of the source file \ndoes not require build process, CoassignViewer \nautomatically skips the build process without \nspecifying this option.''')
parser.add_argument('--assignment-alias',
                    help='specify ASSIGNMENT_ALIAS for each assignment_dir. \nASSIGNMENT_ALIAS is used when making a sub-directory \nin OUTPUT_DIR and the final report file. \n\
default: "basename" of assignment_dir (bar if \nassignment_dir is /foo/bar/).')
parser.add_argument('--output-dir', default='./output',
                    help='specify OUTPUT_DIR in which the final report file \nand build output files to be generated. \n\
avoid including hangul characters in its full path.\ndefault: ./output')

gArgs = parser.parse_args()

# print gArgs
# exit()

if not gArgs.assignment_alias:
    gArgs.assignment_alias = os.path.basename(os.path.abspath(gArgs.assignment_dir[0]))

if not gArgs.run_only:
    gArgs.run_only = False
else:
    gArgs.run_only = True

submittedFileNames = []
srcFileLists = []
buildRetCodes = []
buildLogs = []
exitTypes = []
stdoutStrs = []

############################################
# main routine

destDir, decode2orig, unzipDirNames = preProcess()

submissionNames = os.listdir(destDir)
for i in range(len(submissionNames)):
    submissionName = submissionNames[i]

    print
    print '%s'%logPrefix
    print '%sSubmission %d / %d: %s'%(logPrefix, i+1, len(submissionNames), submissionName)

    if gArgs.file_layout==0:
        leafDirsInDestDir = [root for root, dirs, files in os.walk(opjoin(destDir, submissionName)) if not dirs]

        for i in range(len(leafDirsInDestDir)):
            leafDir = leafDirsInDestDir[i]

            srcFileName = os.listdir(leafDir)[0]
            projName, ext = os.path.splitext(srcFileName)

            print '%s'%logPrefix
            print '%sProject %d / %d: %s'%(logPrefix, i+1, len(leafDirsInDestDir), projName)

            # build
            print '%sBuilding...'%logPrefix
            buildRetCode, buildLog = build(ext, leafDir, projName, [srcFileName])

            if buildRetCode!=0:
                print '%sBuild error. Go on a next file.'%logPrefix
            else:
                print '%sRunning...'%logPrefix
                exitType, stdoutStr = run(ext, leafDir, projName, gArgs.user_input, gArgs.timeout)
                print '%sDone.'%logPrefix


            # add report data
            submittedFileNames.append(decode2orig[submissionName])

            # full path -> \hagsaeng01\munje2\munje2.c
            destSrcFilePath = opjoin(leafDir, srcFileName)
            destSrcFilePathAfterDestDir = destSrcFilePath.replace(destDir, '')

            # \hagsaeng01\munje2\munje2.c -> \hagsaeng01\munje2.c
            d, f = os.path.split(destSrcFilePathAfterDestDir)
            modifiedDestSrcFilePathAfterDestDir = opjoin(os.path.split(d)[0], f)

            origSrcFilePathAfterAssignDir = decode2orig[modifiedDestSrcFilePathAfterDestDir]

            srcFileLists.append([gArgs.assignment_dir[0] + origSrcFilePathAfterAssignDir])

            buildRetCodes.append(buildRetCode)
            buildLogs.append(buildLog)
            if buildRetCode==0:
                exitTypes.append(exitType)
                stdoutStrs.append(stdoutStr)
            else:
                exitTypes.append(None)
                stdoutStrs.append(None)


# origSubFileNames = os.listdir(origAssignDir)
# for i in range(len(origSubFileNames)):
    # origSubFileName = origSubFileNames[i]
    # origSubFilePath =  opjoin(origAssignDir, origSubFileName)
    # if os.path.isdir(origSubFilePath):
        # continue

    # decodeSubFileName = unidecode(origSubFileName)
    # projName, ext = os.path.splitext(os.path.basename(decodeSubFileName))

    # print
    # print '%s'%logPrefix
    # print '%sSubmission %d / %d: %s'%(logPrefix, i+1, len(origSubFileNames), decodeSubFileName)

    # if gArgs.file_layout==0:
        # # 0 - one source file (.c or .cpp) per each student.
        # workDir = prepare(origSubFilePath, gArgs.output_dir, gArgs.assignment_alias, projName, decodeSubFileName)

        # # prepare workDir
        # workDir = prepare(origSubFilePath, gArgs.output_dir, gArgs.assignment_alias, projName, decodeSubFileName)

        # # get origSrcFileNames, repSrcExt
        # if ext=='.zip':
            # origSrcFileNames, srcExts = unzip(decodeSubFileName)
        # else:
            # origSrcFileNames = [origSubFileName]
            # srcExts = [ext]
        # repSrcExt = srcExts[0]

        # # unidecode srcFiles
        # srcFileNames = []
        # for i in range(len(origSrcFileNames)):
            # srcFileName = unidecode(origSrcFileNames[i]) 
            # shutil.move(opjoin(workDir, origSrcFileNames[i]), opjoin(workDir, srcFileName))
            # srcFileNames.append(srcFileName)

        # # build
        # print '%sBuilding...'%logPrefix
        # buildRetCode, buildLog = build(repSrcExt, workDir, projName, srcFileNames)

        # if buildRetCode!=0:
            # print '%sBuild error. Go on a next file.'%logPrefix
        # else:
            # print '%sRunning...'%logPrefix
            # exitType, stdoutStr = run(repSrcExt, workDir, projName, gArgs.user_input, gArgs.timeout)
            # print '%sDone.'%logPrefix

        # # add report data
        # submittedFileNames.append(origSubFileName)
        # srcFileLists.append([opjoin(origAssignDir, origSrcFileName) for origSrcFileName in origSrcFileNames])
        # buildRetCodes.append(buildRetCode)
        # buildLogs.append(buildLog)
        # if buildRetCode==0:
            # exitTypes.append(exitType)
            # stdoutStrs.append(stdoutStr)
        # else:
            # exitTypes.append(None)
            # stdoutStrs.append(None)


    # # elif fileLayout==1:
        # # # 1 - multiple programs (zipped) per each student (one file per each program)
        # # infileNames = unzip(decodeSubFileName)
        # # for infileName in infileNames:
            # # inprojName, ext = os.path.splitext(os.path.basename(infileName))
            # # projName += inprojName

print
print '%s'%logPrefix
print '%sGenerating Report for %s...'%(logPrefix, gArgs.assignment_alias)
generateReport(gArgs, submittedFileNames, \
                srcFileLists, buildRetCodes, buildLogs, exitTypes, stdoutStrs)
postProcess(unzipDirNames)
print '%sDone.'%logPrefix
