package de.htwg.se.muehle
package aview


import de.htwg.se.muehle.controller.controllerInterface
import de.htwg.se.muehle.model.GameStateEnum
import de.htwg.se.muehle.model.gameComponent.Game
import util.Observer
import de.htwg.se.muehle.util.Event
import de.htwg.se.muehle.util.Event.{Load, Save}

import scala.io.StdIn

class Tui(controller: controllerInterface) extends Observer {
  controller.add(this)

  def run(): Unit = {
    while (true) {
      println("Bitte geben Sie Ihren Befehl ein:")
      try {
        val textInput: String = StdIn.readLine()
        val textProcessing: Array[String] = textInput.split(" ")
        if (textProcessing.length == 1) {
          textProcessing(0) match {
            case "undo" => controller.undo()
            case "quit" => println("Auf Wiedersehen!")
              sys.exit(0)
            case "exit" => println("Auf Wiedersehen!")
              return
            case "save" => controller.save()
            case "load" => controller.load()
            case _ => println("Error falsches Eingabeformat")
          }
        } else if (textProcessing.length == 2) {
          getCoords(textProcessing(1)) match {
            case Some(coords) =>
              textProcessing(0) match {
                case "set" => println(s"try to set Stone at: (${coords(0)(0)}, ${coords(0)(1)})")
                  controller.setStone(coords(0)(0), coords(0)(1))
                  if(controller.getGame.asInstanceOf[Game].currentGameState == GameStateEnum.REMOVE_STONE) {
                    muehle()
                  }
                case "move" => println(s"try to move from: (${coords(0)(0)}, ${coords(0)(1)}) to (${coords(1)(0)}, ${coords(1)(1)})")
                  controller.moveStone(coords(0)(0), coords(0)(1), coords(1)(0), coords(1)(1))
                  if(controller.getGame.asInstanceOf[Game].currentGameState == GameStateEnum.REMOVE_STONE) {
                    muehle()
                  }
                case "jump" => println(s"try to jump from: (${coords(0)(0)}, ${coords(0)(1)}) to (${coords(1)(0)}, ${coords(1)(1)})")
                  controller.jumpStone(coords(0)(0), coords(0)(1), coords(1)(0), coords(1)(1))
                  if(controller.getGame.asInstanceOf[Game].currentGameState == GameStateEnum.REMOVE_STONE) {
                    muehle()
                  }
                case "remove" => println(s"try to remove Stone at: (${coords(0)(0)}, ${coords(0)(1)})")
                  controller.removeStone(coords(0)(0), coords(0)(1))
                case _ => println("Error falsches Eingabeformat")
              }
            case None => println("Error falsches Eingabeformat")
          }
        } else {
          println("Error falsches Eingabeformat")
        }
      } catch {
        case e: ArrayIndexOutOfBoundsException => println("Error falsches Eingabeformat")
        case e: Exception => println("Error falsches Eingabeformat")
      }
    }
  }

  def muehle(): Unit = {
    println("Mühle gefunden!")
    println("Bitte geben Sie die Koordinaten des Steins ein, den Sie entfernen möchten:")
  }
  def getCoords(input: String): Option[Array[Array[Int]]] = {
    val coords = input.split(";")
    try {
      if (coords.length == 2) {
        val oldCoords = coords(0).split(",").map(_.toInt)
        val newCoords = coords(1).split(",").map(_.toInt)
        Some(Array(oldCoords, newCoords))
      } else if (coords.length == 1 && coords(0).contains(",")) {
        val oldCoords = coords(0).split(",").map(_.toInt)
        Some(Array(oldCoords))
      } else {
        Some(Array(Array(0, 0)))
      }
    } catch {
      case _: NumberFormatException => None
    }
  }

  override def update(e: Event): Unit = {
    controller.setDecorator(true) // Dekorator ausschalten
    e match {
      case Event.Set =>
        println(controller.getMesh().render())
        println(controller.getGame.asInstanceOf[Game].message.get)
      case Event.GameOver => println("Spiel ist vorbei")
      case Save => println("Spiel gespeichert")

      case Load => println("Spiel geladen")
        println(controller.getMesh().render())
        println(controller.getGame.asInstanceOf[Game].message.get)
    }
  }
}