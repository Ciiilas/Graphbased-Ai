package de.htwg.se.muehle.model.gamefield

import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import org.scalatest.matchers.should.Matchers.*
import org.scalatest.wordspec.AnyWordSpec

class GamefieldSpec extends AnyWordSpec {
/*  "mesh should return correct string representation for default gamefield" in {
    val gamefield = new Gamefield()
    val expectedMesh = "\n0─────0─────0\n" +
      "│     │     │\n" +
      "│ 0───0───0 │\n" +
      "│ │   │   │ │\n" +
      "│ │ 0─0─0 │ │\n" +
      "│ │ │   │ │ │\n" +
      "0─0─0   0─0─0\n" +
      "│ │ │   │ │ │\n" +
      "│ │ 0─0─0 │ │\n" +
      "│ │   │   │ │\n" +
      "│ 0───0───0 │\n" +
      "│     │     │\n" +
      "0─────0─────0\n"
    gamefield.mesh() should be(expectedMesh)
  }*/

 

  "should change muehlematrix" in {
    val field = new Gamefield("EEEEEEEE", 1, 8)
    field.withEnumAt(0, 0, Stone.White) should be(new Gamefield("WEEEEEEE", 1, 8))
  }
  "should made a bar left" in {
    val field = new Gamefield()
    field.barSegmentLeft(2) should be("0─────")
  }
  "should made a bar right" in {
    val field = new Gamefield()
    field.barSegmentRight(2) should be("─────0")
  }
  "should made a spacer left top" in {
    val field = new Gamefield()
    field.spacerLeftTop(2) should be("│ │ ")
  }
  "should made a spacer right top" in {
    val field = new Gamefield()
    field.spacerRightTop(2) should be(" │ │")
  }
  "should made a spacer left bottom" in {
    val field = new Gamefield()
    field.spacerLeftBottom(2) should be("│ │ ")
  }
  "should made a spacer right bottom" in {
    val field = new Gamefield()
    field.spacerRightBottom(2) should be(" │ │")
  }

  "should made a segemnt left bottom" in {
    val field = new Gamefield()
    field.barSegmentLeftBottom(2) should be("0─────")
  }
  "should made a segemnt right bottom" in {
    val field = new Gamefield()
    field.barSegmentRightBottom(2) should be("─────0")
  }
}