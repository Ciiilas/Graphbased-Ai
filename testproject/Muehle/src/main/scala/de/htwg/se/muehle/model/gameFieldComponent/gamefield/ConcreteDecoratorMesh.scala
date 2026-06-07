package de.htwg.se.muehle.model.gameFieldComponent.gamefield

//Konkreter Dekorator
case class ConcreteDecoratorMesh(wrappee: meshComponentInterface) extends meshComponentInterface {
  override def render(): String = {
    val title = "Mühle-Spiel\n"
    val border = "=====================\n"
    title + border + wrappee.render() + border
  }
}
