package de.htwg.se.muehle.model.FileIOComponent

import de.htwg.se.muehle.model.gameInterface

trait FileIOComponent {
  
  def load(): gameInterface
  def save(game: gameInterface): Unit

}
