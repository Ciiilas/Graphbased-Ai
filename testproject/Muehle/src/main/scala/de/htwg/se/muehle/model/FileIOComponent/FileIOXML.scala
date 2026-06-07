package de.htwg.se.muehle.model.FileIOComponent

import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.{GameStateEnum, gameFieldComponent, gameInterface, mechanicComponent}
import de.htwg.se.muehle.model.mechanicComponent.mechanic.Mechanic
import de.htwg.se.muehle.model.gameComponent.{Game, PlayerState}
import java.io.{File, PrintWriter}
import scala.xml.{Elem, PrettyPrinter}

class FileIOXML extends FileIOComponent {

  override def load(): gameInterface = {
    val file = scala.xml.XML.loadFile("SaveGame.xml")

    val gameState = (file \\ "gameState").text match {
      case "Stein setzen" => GameStateEnum.SET_STONE
      case "Stein bewegen" => GameStateEnum.MOVE_STONE
      case "Stein springen" => GameStateEnum.JUMP_STONE
      case "Stein entfernen" => GameStateEnum.REMOVE_STONE
      case _ => GameStateEnum.GAME_OVER
    }

    val currentPlayer = (file \\ "currentPlayer").text match {
      case "W" => Stone.White
      case "B" => Stone.Black
      case _ => Stone.Empty
    }
    PlayerState.stone = currentPlayer

    val message = (file \\ "message").text

    val muehleMatrix = (file \\ "gameField" \\ "row").map(row =>
      (row \\ "cell").map(cell => cell.text match {
        case "W" => Stone.White
        case "B" => Stone.Black
        case "0" => Stone.Empty
      }).toVector
    ).toVector
    val gameField = Gamefield(muehleMatrix)

    val counterOfSetStone = (file \\ "mechanic" \\ "counterOfSetStone").text.toInt
    val mechanic = Mechanic(counterOfSetStone)

    Game(mechanic, gameField, Some(message), currentPlayer, gameState)
  }

  override def save(game: gameInterface): Unit = {
    val gameField = game.getGameField.getMuehleMatrix.map(row =>
      <row>{row.map(cell => <cell>{cell.toString}</cell>)}</row>
    )

    val data: Elem =
      <game>
        <gameState>{game.getCurrentGameState.toString}</gameState>
        <currentPlayer>{game.getPlayer.toString}</currentPlayer>
        <message>{game.getMessage.getOrElse("")}</message>
        <gameField>{gameField}</gameField>
        <mechanic>
          <counterOfSetStone>{game.getMechanic.getCounterOfSetStone}</counterOfSetStone>
        </mechanic>
      </game>

    val prettyPrinter = new PrettyPrinter(120, 4)
    val xmlString = prettyPrinter.format(data)

    val pw = new PrintWriter(new File("SaveGame.xml"))
    pw.write(xmlString)
    pw.close()
  }
}