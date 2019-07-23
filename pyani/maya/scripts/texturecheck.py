import maya.cmds as mc
import os


def texture_status(printAllTex=False, printAllTexDirs=False, printMissingTex=False):
    texDirs = []
    missingTex = []
    fileList = mc.ls(type="file")

    if printAllTex:
        # prints out all files and their absolute path.
        print "\n========= ALL TEXTURES SCENE IS LOOKING FOR ==============="

    for f in fileList:
        fPath = mc.getAttr(f + ".fileTextureName")

        dirPath = os.path.split(fPath)[0]

        missingTex.append(fPath)

        if printAllTex:
            print f + ":"
            print fPath + "\n"

        if dirPath not in texDirs:
            texDirs.append(dirPath)

    # print the number of textures
    print "\n========= TEXTURE COUNT  ====================================="
    print "Found", str(len(fileList)), "textures in the scene:\n"

    # prints missing texture files
    if printMissingTex:
        print "\n========= MISSING TEXTURES ==============================="
        for f in missingTex:
            try:
                if not os.path.exists(f):
                    print f
            except OSError:
                print "Problem parsing texture: {0}".format(f)

    if printAllTexDirs:
        # prints out all folders being used for the textures
        print "\n========= ALL TEXTURE FOLDERS SCENE REFERENCES ======="
        for d in texDirs:
            print d

    # prints out the folder if file doesn't exist
    print "\n========= MISSING TEXTURE FOLDERS ========================"
    for d in texDirs:
        try:
            if not os.path.exists(d):
                print d
        except OSError:
            print "Problem parsing folder: {0}".format(d)

    print "\n========= EMPTY TEXTURE FOLDERS =========================="
    for d in texDirs:
        try:
            if os.path.exists(d) and len(os.listdir(d)) == 0:
                print  d
        except OSError:
            print "Problem parsing folder: {0}".format(d)


'''
HELP:
To see all textures scene expects: texture_status(printAllTex=True)
To see all texure folders expected: texture_status(printAllTexDirs=True)
To see a list of all missing textures texture_status(printMissingTex=True)
You can combine these as well, for example: texture_status(printAllTex=True, printAllTexDirs=True)

'''
# run the function
texture_status()