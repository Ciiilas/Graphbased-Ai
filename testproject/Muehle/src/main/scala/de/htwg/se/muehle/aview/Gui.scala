package de.htwg.se.muehle
package aview

import de.htwg.se.muehle.controller.controllerComponent.Controller
import scala.swing.*
import java.awt.{Color, Graphics2D}
import scala.swing.event.MouseClicked
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Stone
import de.htwg.se.muehle.util.Observer
import de.htwg.se.muehle.util.Event
import de.htwg.se.muehle.model.GameStateEnum
import de.htwg.se.muehle.model.gameComponent.Game

class Gui(controller: Controller) extends SimpleSwingApplication with Observer {
  controller.add(this)

  private val messageLable: Label = new Label {
    text = "Willkommen zu Mühle"
    preferredSize = new Dimension(600, 50)
  }
  
  private val boardPanel: Panel = new Panel {
    preferredSize = new Dimension(600, 600)

    val margin = 50
    val boardSize = 500
    val step: Int = boardSize / 3

    val outer: Int = margin
    val middle: Int = margin + step / 2
    val inner: Int = margin + step

    val sizeOuter: Int = boardSize
    val sizeMiddle: Int = boardSize - step
    val sizeInner: Int = boardSize - 2 * step

    val centerX: Int = margin + boardSize / 2
    val centerY: Int = margin + boardSize / 2

    val outerSquare: Vector[(Int, Int)] = Vector(
      (outer, outer), (centerX, outer), (outer + sizeOuter, outer),
      (outer + sizeOuter, centerY), (outer + sizeOuter, outer + sizeOuter),
      (centerX, outer + sizeOuter), (outer, outer + sizeOuter), (outer, centerY)
    )

    val middleSquare: Vector[(Int, Int)] = Vector(
      (middle, middle), (centerX, middle), (middle + sizeMiddle, middle),
      (middle + sizeMiddle, centerY), (middle + sizeMiddle, middle + sizeMiddle),
      (centerX, middle + sizeMiddle), (middle, middle + sizeMiddle), (middle, centerY)
    )

    val innerSquare: Vector[(Int, Int)] = Vector(
      (inner, inner), (centerX, inner), (inner + sizeInner, inner),
      (inner + sizeInner, centerY), (inner + sizeInner, inner + sizeInner),
      (centerX, inner + sizeInner), (inner, inner + sizeInner), (inner, centerY)
    )

    val allSquares: Vector[Vector[(Int, Int)]] = Vector(innerSquare, middleSquare, outerSquare)

    private var firstClick: Option[(Int, Int)] = None
    
    override def paintComponent(g: Graphics2D): Unit = {
      super.paintComponent(g)
      drawMuehleBoard(g) // Zeichnet den Rahmen um den geklickten Punkt
      }

    def drawMuehleBoard(g: Graphics2D): Unit = {
      g.setColor(new Color(255, 255, 200))
      g.fillRect(0, 0, size.width, size.height)


      g.setColor(Color.BLACK)
      for (i <- 0 to 2) {
        val offset = margin + i * step / 2
        val size = boardSize - i * step
        g.drawRect(offset, offset, size, size)
      }


      g.drawLine(outer, centerY, inner, centerY)
      g.drawLine(outer + sizeOuter, centerY, inner + sizeInner, centerY)
      g.drawLine(centerX, outer, centerX, inner)
      g.drawLine(centerX, outer + sizeOuter, centerX, inner + sizeInner)

      drawClickedPointBorder(g)

      for ((square, squareIndex) <- allSquares.zipWithIndex) {
        for (((x, y), pointIndex) <- square.zipWithIndex) {
          val stone = controller.getMuehleMatrix(squareIndex)(pointIndex)
          stone match {
            case Stone.Empty =>
              g.setColor(Color.BLACK)
              g.drawOval(x - 10, y - 10, 20, 20)
              g.setColor(Color.WHITE)
              g.fillOval(x - 10, y - 10, 20, 20)
            case Stone.White =>
              g.setColor(Color.RED)
              g.fillOval(x - 10, y - 10, 20, 20)
            case Stone.Black =>
              g.setColor(Color.BLACK)
              g.fillOval(x - 10, y - 10, 20, 20)
          }
        }
      }
    }

    private var clickedPoint: Option[(Int, Int)] = None

    def drawClickedPointBorder(g: Graphics2D): Unit = {
      clickedPoint.foreach { case (x, y) =>
        g.setColor(Color.BLUE)
        g.fillOval(x - 15, y - 15, 30, 30)
      }
    }

    listenTo(mouse.clicks)
    reactions += {
      case MouseClicked(_, point, _, _, _) =>
      val clickedPoint = (point.x, point.y)

      val (squareIndex, (pointIndex, closestPoint)) = allSquares.zipWithIndex.flatMap {
        case (square, index) =>
          square.zipWithIndex.map { case (p, pointIdx) => (index, (pointIdx, p)) }
      }.minBy {
        case (_, (_, (x, y))) => math.sqrt(math.pow(x - clickedPoint._1, 2) + math.pow(y - clickedPoint._2, 2))
      }

      val radius = 40
      val distance = math.sqrt(math.pow(closestPoint._1 - clickedPoint._1, 2) + math.pow(closestPoint._2 - clickedPoint._2, 2))
      if (distance <= radius) {
        this.clickedPoint = Some(closestPoint)
        this.repaint()
        controller.getGameState match {
          case GameStateEnum.SET_STONE =>
            controller.setStone(squareIndex, pointIndex)
          case GameStateEnum.MOVE_STONE =>
            firstClick match {
              case None =>
                firstClick = Some((squareIndex, pointIndex))
              case Some((x, y)) =>
                controller.moveStone(x, y, squareIndex, pointIndex)
                firstClick = None
            }
          case GameStateEnum.JUMP_STONE =>
            firstClick match {
              case None =>
                firstClick = Some((squareIndex, pointIndex))
              case Some((x, y)) =>
                controller.jumpStone(x, y, squareIndex, pointIndex)
                firstClick = None
            }
          case GameStateEnum.REMOVE_STONE =>
            controller.removeStone(squareIndex, pointIndex)
          case GameStateEnum.GAME_OVER =>
            controller.sendGameOver(Option("Game is over"))
        }
      }
    }
  }

  def top: MainFrame = new MainFrame {
    title = "Mühle-Spielfeld"
    menuBar = new MenuBar {
      contents += new Menu("File") {
        contents += new MenuItem(Action("Undo") {
          println("trigger undo")
          controller.undo() // Undo-Funktion aufrufen
          repaint()
        })
        contents += new MenuItem(Action("Exit") {
          sys.exit(0) // Beendet das Programm
        })
        contents += new MenuItem(Action("Load") {
          controller.load() // Undo-Funktion aufrufen
        })
        contents += new MenuItem(Action("Save") {
          controller.save() // Undo-Funktion aufrufen
        })
      }
    }
    contents = new BorderPanel {
      layout(boardPanel) = BorderPanel.Position.Center
      layout(messageLable) = BorderPanel.Position.South
    }
  }

  // Observer Update-Methode
  override def update(e: Event): Unit = {
    e match
      case Event.Set =>
        messageLable.text = controller.game.asInstanceOf[Game].message.getOrElse("Mühle-Spielfeld")
        boardPanel.repaint()

      case Event.GameOver =>
        messageLable.text = "Game Over"
        boardPanel.repaint()

      case Event.Load =>
        messageLable.text = "Load"
        boardPanel.repaint()

      case Event.Save =>
        messageLable.text = "Save"
        boardPanel.repaint()

      case Event.Quit =>
        sys.exit(0)
        boardPanel.repaint()
  }
}
