package de.htwg.se.muehle

import com.google.inject.{AbstractModule, TypeLiteral}
import de.htwg.se.muehle.controller.controllerComponent.Controller
import de.htwg.se.muehle.model.{GameStateEnum, gameInterface}
import de.htwg.se.muehle.controller.controllerInterface
import de.htwg.se.muehle.model.FileIOComponent.{FileIOComponent, FileIOJSON, FileIOXML}
import de.htwg.se.muehle.model.gameComponent.Game
import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.{Gamefield, Stone}
import de.htwg.se.muehle.model.mechanicComponent.mechanicInterface
import de.htwg.se.muehle.model.mechanicComponent.mechanic.{ComplexEvaluateStrategy, EvaluateStrategy, Mechanic}


class MuehleModule extends AbstractModule {
  override def configure(): Unit = {
    bind(classOf[controllerInterface]).to(classOf[Controller])
    bind(classOf[gameInterface]).to(classOf[Game])
    bind(classOf[gameFieldInterface]).to(classOf[Gamefield])
    bind(classOf[mechanicInterface]).to(classOf[Mechanic])
    bind(classOf[GameStateEnum]).toInstance(GameStateEnum.SET_STONE)
    bind(classOf[Stone]).toInstance(Stone.White)
    bind(new TypeLiteral[Option[String]]() {}).toInstance(None)
    bind(classOf[EvaluateStrategy]).to(classOf[ComplexEvaluateStrategy])
    bind(classOf[Int]).toInstance(0)
    bind(classOf[FileIOComponent]).to(classOf[FileIOXML])
  }
}