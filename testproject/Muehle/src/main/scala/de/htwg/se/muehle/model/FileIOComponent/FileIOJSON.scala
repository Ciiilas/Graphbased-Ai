package de.htwg.se.muehle.model.FileIOComponent

import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.{GameStateEnum, gameFieldComponent, gameInterface, mechanicComponent}
import de.htwg.se.muehle.model.mechanicComponent.mechanic.Mechanic
import de.htwg.se.muehle.model.gameComponent.{Game, PlayerState}
import play.api.libs.json.*

import java.io.*
import scala.io.BufferedSource


class FileIOJSON extends FileIOComponent {
  
  override def load(): gameInterface = {
    val source: BufferedSource = scala.io.Source.fromFile("SaveGame.json")
    val jsonString = try {
      source.mkString
    } catch {
      case e: IOException => throw new RuntimeException("Error reading the file: " + e.getMessage, e)
    } finally source.close()
    val json = Json.parse(jsonString)

    val gameState = (json \ "gameState").as[String] match {
      case "Stein setzen" => GameStateEnum.SET_STONE
      case "Stein bewegen" => GameStateEnum.MOVE_STONE
      case "Stein springen" => GameStateEnum.JUMP_STONE
      case "Stein entfernen" => GameStateEnum.REMOVE_STONE
      case _ => GameStateEnum.GAME_OVER
    }
    
    val currentPlayer = (json \ "currentPlayer").as[String] match {
      case "W" => Stone.White
      case "B" => Stone.Black
      case _ => Stone.Empty
    }
    PlayerState.stone = currentPlayer
    
    val message = (json \ "message").as[String]
    
    
    val muehleMatrix = (json \ "gameField").as[Vector[Vector[String]]].map(_.map {
      case "W" => Stone.White
      case "B" => Stone.Black
      case "0" => Stone.Empty
    })
    val gameField = Gamefield(muehleMatrix)
    
    val counterOfSetStone = (json \ "mechanic" \ "counterOfSetStone").as[Int]
    val mechanic = Mechanic(counterOfSetStone)
    
    Game(mechanic, gameField, Some(message), currentPlayer, gameState)
  }

  
  
  override def save(game: gameInterface): Unit = {
    val json: JsValue = Json.obj(
      "gameState" -> game.getCurrentGameState.toString,
      "currentPlayer" -> game.getPlayer.toString,
      "message" -> game.getMessage,
      "gameField" -> Json.toJson(
      game.getGameField.getMuehleMatrix.map(_.map(_.toString))
      ),
      "mechanic" -> Json.obj(
        "counterOfSetStone" -> game.getMechanic.getCounterOfSetStone,
      )
    )
    val pw = new PrintWriter(new File("SaveGame.json"))
    pw.write(Json.prettyPrint(json))
    pw.close()
  }
}
