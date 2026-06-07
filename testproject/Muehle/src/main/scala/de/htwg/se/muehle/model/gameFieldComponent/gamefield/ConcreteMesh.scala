package de.htwg.se.muehle.model.gameFieldComponent.gamefield

//Basis-Komponente(Concrete Component)
case class ConcreteMesh(model: Gamefield) extends meshComponentInterface {
  override def render(): String = model.mesh()
}
