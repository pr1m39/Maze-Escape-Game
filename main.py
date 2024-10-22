from direct.showbase.ShowBase import ShowBase
from panda3d.core import CollisionTraverser, CollisionNode
from panda3d.core import CollisionHandlerQueue, CollisionRay
from panda3d.core import Material, LRotationf, NodePath
from panda3d.core import AmbientLight, DirectionalLight
from panda3d.core import TextNode
from panda3d.core import LVector3, BitMask32
from direct.gui.OnscreenText import OnscreenText
from direct.interval.MetaInterval import Sequence, Parallel
from direct.interval.LerpInterval import LerpFunc
from direct.interval.FunctionInterval import Func, Wait
from direct.task.Task import Task
import sys
from panda3d.core import Point3
from direct.gui.DirectGui import DirectButton, DirectFrame


ACCEL = 70  # Acceleration constant
MAX_SPEED = 5  # Max speed constant
MAX_SPEED_SQ = MAX_SPEED ** 2  # Max speed squared


class MazeEscape(ShowBase):

    def __init__(self):
        ShowBase.__init__(self)

        self.title = OnscreenText(text="Maze Escape", parent=base.a2dBottomRight, align=TextNode.ARight,
                                  fg=(1, 1, 1, 1), pos=(-0.1, 0.1), scale=.08, shadow=(0, 0, 0, 0.5))
        self.instructions = OnscreenText(text="Move the Maze to Escape", parent=base.a2dTopLeft,
                                         align=TextNode.ALeft, pos=(0.05, -0.08), fg=(1, 1, 1, 1),
                                         scale=.06, shadow=(0, 0, 0, 0.5))

        self.accept("escape", sys.exit)

        self.disableMouse()
        camera.setPosHpr(0, 0, 25, 0, -90, 0)

        self.maze = loader.loadModel("models/maze")
        self.maze.reparentTo(render)

        self.walls = self.maze.find("**/wall_collide")
        self.walls.node().setIntoCollideMask(BitMask32.bit(0))

        self.loseTriggers = []
        for i in range(6):
            trigger = self.maze.find("**/hole_collide" + str(i))
            trigger.node().setIntoCollideMask(BitMask32.bit(0))
            trigger.node().setName("loseTrigger")
            self.loseTriggers.append(trigger)

        self.mazeGround = self.maze.find("**/ground_collide")
        self.mazeGround.node().setIntoCollideMask(BitMask32.bit(1))

        self.ballRoot = render.attachNewNode("ballRoot")
        self.ball = loader.loadModel("models/ball")
        self.ball.reparentTo(self.ballRoot)

        self.ballSphere = self.ball.find("**/ball")
        self.ballSphere.node().setFromCollideMask(BitMask32.bit(0))
        self.ballSphere.node().setIntoCollideMask(BitMask32.allOff())

        self.ballGroundRay = CollisionRay()
        self.ballGroundRay.setOrigin(0, 0, 10)
        self.ballGroundRay.setDirection(0, 0, -1)

        self.ballGroundCol = CollisionNode('groundRay')
        self.ballGroundCol.addSolid(self.ballGroundRay)
        self.ballGroundCol.setFromCollideMask(BitMask32.bit(1))
        self.ballGroundCol.setIntoCollideMask(BitMask32.allOff())

        self.ballGroundColNp = self.ballRoot.attachNewNode(self.ballGroundCol)

        self.cTrav = CollisionTraverser()
        self.cHandler = CollisionHandlerQueue()

        self.cTrav.addCollider(self.ballSphere, self.cHandler)
        self.cTrav.addCollider(self.ballGroundColNp, self.cHandler)

        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor((.55, .55, .55, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setDirection(LVector3(0, 0, -1))
        directionalLight.setColor((0.375, 0.375, 0.375, 1))
        directionalLight.setSpecularColor((1, 1, 1, 1))
        self.ballRoot.setLight(render.attachNewNode(ambientLight))
        self.ballRoot.setLight(render.attachNewNode(directionalLight))

        m = Material()
        m.setSpecular((1, 1, 1, 1))
        m.setShininess(96)
        self.ball.setMaterial(m, 1)

        self.mainMenu()  # Start with the main menu

    def mainMenu(self):
        # Destroy any existing UI elements before creating new ones
        self.clearUI()

        # Create a frame for the main menu
        self.menuFrame = DirectFrame(frameColor=(0, 0, 0, 0.5), frameSize=(-1, 1, -1, 1))

        # Start Game button
        self.startButton = DirectButton(text="Start Game", scale=0.1, command=self.startGame, pos=(0, 0, 0.1))

        # Quit button
        self.quitButton = DirectButton(text="Quit", scale=0.1, command=sys.exit, pos=(0, 0, -0.1))

    def clearUI(self):
        """Helper function to clear any existing UI elements."""
        if hasattr(self, 'menuFrame'):
            self.menuFrame.destroy()
        if hasattr(self, 'victoryFrame'):
            self.victoryFrame.destroy()
        if hasattr(self, 'startButton'):
            self.startButton.destroy()
        if hasattr(self, 'quitButton'):
            self.quitButton.destroy()
        if hasattr(self, 'victoryText'):
            self.victoryText.destroy()
        if hasattr(self, 'playAgainButton'):
            self.playAgainButton.destroy()

    def startGame(self):
        # Clear the UI when the game starts
        self.clearUI()
        self.start()

    def start(self):
        startPos = self.maze.find("**/start").getPos()
        self.ballRoot.setPos(startPos)
        self.ballV = LVector3(0, 0, 0)
        self.accelV = LVector3(0, 0, 0)

        taskMgr.remove("rollTask")
        self.mainLoop = taskMgr.add(self.rollTask, "rollTask")

    def rollTask(self, task):
        dt = globalClock.getDt()
        if dt > .2:
            return Task.cont

        for i in range(self.cHandler.getNumEntries()):
            entry = self.cHandler.getEntry(i)
            name = entry.getIntoNode().getName()
            if name == "wall_collide":
                self.wallCollideHandler(entry)
            elif name == "ground_collide":
                self.groundCollideHandler(entry)
            elif name == "loseTrigger":
                self.loseGame(entry)

        if base.mouseWatcherNode.hasMouse():
            mpos = base.mouseWatcherNode.getMouse()
            self.maze.setP(mpos.getY() * -10)
            self.maze.setR(mpos.getX() * 10)

        self.ballV += self.accelV * dt * ACCEL

        if self.ballV.lengthSquared() > MAX_SPEED_SQ:
            self.ballV.normalize()
            self.ballV *= MAX_SPEED

        self.ballRoot.setPos(self.ballRoot.getPos() + (self.ballV * dt))

        prevRot = LRotationf(self.ball.getQuat())
        axis = LVector3.up().cross(self.ballV)
        newRot = LRotationf(axis, 45.5 * dt * self.ballV.length())
        self.ball.setQuat(prevRot * newRot)

        # Check if the ball reached the goal
        if self.ballRoot.getPos().almostEqual(Point3(5, 5, 0), 0.5):  # Replace with actual goal coordinates
            self.victoryScreen()

        return Task.cont

    def wallCollideHandler(self, colEntry):
        norm = colEntry.getSurfaceNormal(render) * -1  # Get the surface normal at the point of collision
        curSpeed = self.ballV.length()  # Get current ball speed
        inVec = self.ballV / curSpeed  # Normalize the current velocity vector
        velAngle = norm.dot(inVec)  # Angle between the velocity and normal
        hitDir = colEntry.getSurfacePoint(render) - self.ballRoot.getPos()
        hitDir.normalize()

        hitAngle = norm.dot(hitDir)

        # Reflect the velocity if the collision is with a wall and the ball is moving towards it
        if velAngle > 0 and hitAngle > .995:
            reflectVec = (norm * norm.dot(inVec * -1) * 2) + inVec  # Calculate reflection vector
            self.ballV = reflectVec * (curSpeed * (((1 - velAngle) * .5) + .5))
            disp = (colEntry.getSurfacePoint(render) -
                    colEntry.getInteriorPoint(render))
            newPos = self.ballRoot.getPos() + disp
            self.ballRoot.setPos(newPos)

    def groundCollideHandler(self, colEntry):
        newZ = colEntry.getSurfacePoint(render).getZ()
        self.ballRoot.setZ(newZ + .4)

        norm = colEntry.getSurfaceNormal(render)
        accelSide = norm.cross(LVector3.up())
        self.accelV = norm.cross(accelSide)

    def victoryScreen(self):
        self.clearUI()  # Hide any existing UI before showing victory screen
        self.victoryFrame = DirectFrame(frameColor=(0, 0, 0, 0.5), frameSize=(-1, 1, -1, 1))
        self.victoryText = OnscreenText(text="You Win!", scale=0.2, fg=(1, 1, 1, 1), pos=(0, 0.2))
        self.playAgainButton = DirectButton(text="Play Again", scale=0.1, command=self.resetGame, pos=(0, 0, -0.1))

    def resetGame(self):
        self.clearUI()  # Hide victory screen before resetting the game
        self.mainMenu()

    def loseGame(self, entry):
        toPos = entry.getInteriorPoint(render)
        taskMgr.remove('rollTask')
        Sequence(
            Parallel(
                LerpFunc(self.ballRoot.setX, fromData=self.ballRoot.getX(), toData=toPos.getX(), duration=.1),
                LerpFunc(self.ballRoot.setY, fromData=self.ballRoot.getY(), toData=toPos.getY(), duration=.1),
                LerpFunc(self.ballRoot.setZ, fromData=self.ballRoot.getZ(), toData=self.ballRoot.getZ() - .9,
                         duration=.2)
            ),
            Wait(1),
            Func(self.start)
        ).start()


demo = MazeEscape()
demo.run()
