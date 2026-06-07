package de.htwg.se.muehle.model.mechanic

import de.htwg.se.muehle.model.gameComponent.Game
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.mechanicComponent.mechanic.Mechanic
import org.scalatest.matchers.should.Matchers.*
import org.scalatest.wordspec.AnyWordSpec

class MechanicSpec extends AnyWordSpec {
  "Mechanic" should {
    
    val game = new Game()
    
    "recognise if move is allowed or not" in {
      game.mech.isMoveAllowed(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 1) should be(true)
      game.mech.isMoveAllowed(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 2) should be(false)
    }
    "count the number of stones" in {
      game.mech.countStones(new Gamefield("WWWBBBBB", 1, 8), Stone.Black) should be(5)
      game.mech.countStones(new Gamefield("WWWBBBBB", 2, 8), Stone.Black) should be(5)
      game.mech.countStones(new Gamefield("WWWBBBBB", 1, 8), Stone.White) should be(3)
      game.mech.countStones(new Gamefield("WWWBBBBB", 2, 8), Stone.Black) should be(5)
    }
    "recognise if set is allowed or not" in {
      game.mech.isSetLegal(new Gamefield("EEEEEEEE", 1, 8), 0, 0) should be(true)
      game.mech.isSetLegal(new Gamefield("EEEEEEEE", 1, 8), 0, 8) should be(false)
    }
/*    "set a Stone" in {
      game.mech.setStone(new Gamefield("EEEEEEEE", 1, 8), 0, 0, Stone.White) should be(new Gamefield("WEEEEEEE", 1, 8))
      game.mech.setStone(new Gamefield("EEEEEEEEEEEEEEEE", 2, 8), 1, 0, Stone.White) should be(new Gamefield("EEEEEEEEWEEEEEEE", 2, 8))
    }*/
    "recognise if move is legal or not" in {
      game.mech.isMoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 1, Stone.White) should be(true)
      game.mech.isMoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 0, Stone.White) should be(false)
      game.mech.isMoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 1, Stone.Black) should be(false)
      game.mech.isMoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 0, Stone.White) should be(false)
    }
    "move a Stone" in {
      game.mech.moveStone(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 1, Stone.White) should be(new Gamefield("EWEEEEEE", 1, 8))
    }
    "recognise if jump is legal or not" in {
      game.mech.isJumpLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 2, Stone.White) should be(true)
      game.mech.isJumpLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 1, Stone.White) should be(true)
      game.mech.isJumpLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 2, Stone.Black) should be(false)
    }
    "jump a stone" in {
      game.mech.jumpStone(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 7, Stone.White) should be(new Gamefield("EEEEEEEW", 1, 8))
      game.mech.jumpStone(new Gamefield("WEEEEEEE", 1, 8), 0, 0, 0, 7, Stone.Black) should be(new Gamefield("WEEEEEEE", 1, 8))
    }
    "recogniss if remove is legal or not" in {
      game.mech.isRemoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, Stone.Black) should be(true)
      game.mech.isRemoveLegal(new Gamefield("WEEEEEEE", 1, 8), 0, 0, Stone.White) should be(false)
    }
    "remove a stone" in {
      game.mech.removeStone(new Gamefield("WEEEEEEE", 1, 8), 0, 0, Stone.Black) should be(new Gamefield("EEEEEEEE", 1, 8))
      game.mech.removeStone(new Gamefield("WEEEEEEE", 1, 8), 0, 0, Stone.White) should be(new Gamefield("WEEEEEEE", 1, 8))
    }

  }

}
