package de.htwg.se.muehle.model

import play.api.libs.json._

enum GameStateEnum(stringRepresentation: String) {
  override def toString: String = stringRepresentation
  case SET_STONE extends GameStateEnum("Stein setzen")
  case MOVE_STONE extends GameStateEnum("Stein bewegen")
  case JUMP_STONE extends GameStateEnum("Stein springen")
  case REMOVE_STONE extends GameStateEnum("Stein entfernen")
  case GAME_OVER extends GameStateEnum("Spiel beendet")
}

object GameStateEnum {
  implicit val writes: Writes[GameStateEnum] = Writes { state => JsString(state.toString) }
  implicit val reads: Reads[GameStateEnum] = Reads {
    case JsString("Stein setzen") => JsSuccess(SET_STONE)
    case JsString("Stein bewegen") => JsSuccess(MOVE_STONE)
    case JsString("Stein springen") => JsSuccess(JUMP_STONE)
    case JsString("Stein entfernen") => JsSuccess(REMOVE_STONE)
    case JsString("Spiel beendet") => JsSuccess(GAME_OVER)
    case _ => JsError("Unknown GameState type")
  }
}