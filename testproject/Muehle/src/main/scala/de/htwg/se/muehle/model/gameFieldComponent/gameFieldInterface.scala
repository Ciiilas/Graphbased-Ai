package de.htwg.se.muehle.model.gameFieldComponent

import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import play.api.libs.json.*

trait gameFieldInterface {
  //Getter
  def getMuehleMatrix: Vector[Vector[Stone]]
  
  def withEnumAt(row: Int, col: Int, newEnum: Stone): gameFieldInterface
  def mesh(): String
  def barSegmentLeft(times: Int): String
  def barSegmentRight(times: Int): String
  def spacerLeftTop(times: Int): String
  def spacerRightTop(times: Int): String
  def spacerLeftBottom(times: Int): String
  def spacerRightBottom(times: Int): String
  def barSegmentLeftBottom(times: Int): String
  def barSegmentRightBottom(times: Int): String
}

object gameFieldInterface {
  implicit val writes: Writes[gameFieldInterface] = Writes {
    case gameField: Gamefield => Json.toJson(gameField)(Gamefield.writes)
    case _ => throw new IllegalArgumentException("Unknown gameFieldInterface implementation")
  }

  implicit val reads: Reads[gameFieldInterface] = Reads {
    json => json.validate[Gamefield](Gamefield.reads)
  }
}