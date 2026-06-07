package de.htwg.se
package muehle

import de.htwg.se.muehle.aview.{Gui, Tui}
import de.htwg.se.muehle.controller.controllerComponent.Controller
import de.htwg.se.muehle.model.gameComponent.Game
import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.Gamefield
import de.htwg.se.muehle.model.gameInterface
import de.htwg.se.muehle.model.mechanicComponent.mechanic.Mechanic
import de.htwg.se.muehle.model.mechanicComponent.mechanicInterface

import com.google.inject.Guice

object Muehle {
  
  def main(args: Array[String]): Unit = {
    val mech: mechanicInterface = new Mechanic
    val gameField: gameFieldInterface = new Gamefield
    val game: gameInterface = Game(mech, gameField)
    val injector = Guice.createInjector(new MuehleModule)
    val controller = injector.getInstance(classOf[Controller])
    val tui = new Tui(controller)
    val simpleSwingGui = new Gui(controller)

    println("Willkommen zu Muehle")
    simpleSwingGui.top.visible = true
    
    tui.run()
  }
}