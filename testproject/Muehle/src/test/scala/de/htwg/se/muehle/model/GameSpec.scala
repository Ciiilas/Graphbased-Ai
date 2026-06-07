package de.htwg.se.muehle.model

import de.htwg.se.muehle.model.gameComponent.Game
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Gamefield
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Stone
import de.htwg.se.muehle.model.gameInterface
import org.scalatest.matchers.should.Matchers.*
import org.scalatest.wordspec.AnyWordSpec

class GameSpec extends AnyWordSpec {
  "Game" should {
    "set a stone" in {
      val game = new Game(new Gamefield("EEEEEEEE", 1, 8))
      game.setStoneGame(0,0).field should be(new Game(new Gamefield("WEEEEEEE", 1, 8)).field)
    }
    "return the mechanic" in {
      val game = new Game()
      game.getMechanic should be(game.mech)
    }
    "return the GameField" in {
      val game = new Game()
      game.getGameField should be(game.field)
    }
    "return the message" in {
      val game = new Game()
      game.getMessage should be(game.message)
    }
    "return the player" in {
      val game = new Game()
      game.getPlayer should be(game.player)
    }
    "return the currentGameState" in {
      val game = new Game()
      game.getCurrentGameState should be(game.currentGameState)
    }
    "return the opponent player" in {
      val game = new Game()
      game.getOpponentPlayer should be(Stone.White)
    }

  }
}
