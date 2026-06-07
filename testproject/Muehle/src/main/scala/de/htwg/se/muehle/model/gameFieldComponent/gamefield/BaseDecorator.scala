package de.htwg.se.muehle.model.gameFieldComponent.gamefield

//Basis-Decorator
abstract class BaseDecorator(component: meshComponentInterface) extends meshComponentInterface {
  protected val wrappee: meshComponentInterface = component

  // Delegiert die Render-Funktion an den Wrappee
  override def render(): String = wrappee.render()
}