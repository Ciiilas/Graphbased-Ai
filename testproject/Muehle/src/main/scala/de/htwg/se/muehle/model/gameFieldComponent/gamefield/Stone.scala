package de.htwg.se.muehle.model.gameFieldComponent.gamefield

import play.api.libs.json._

enum Stone(stringRepresentation: String):
  override def toString: String = stringRepresentation
  case White extends Stone("W")
  case Black extends Stone("B")
  case Empty extends Stone("0")

object Stone {
  implicit val writes: Writes[Stone] = Writes { stone => JsString(stone.toString) }
  implicit val reads: Reads[Stone] = Reads {
    case JsString("W") => JsSuccess(White)
    case JsString("B") => JsSuccess(Black)
    case JsString("0") => JsSuccess(Empty)
    case _ => JsError("Unknown Stone type")
  }
}