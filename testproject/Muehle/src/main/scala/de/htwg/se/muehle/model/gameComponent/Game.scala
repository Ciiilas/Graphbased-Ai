package de.htwg.se.muehle.model.gameComponent


import com.google.inject.Inject
import de.htwg.se.muehle.model.gameFieldComponent.gameFieldInterface
import de.htwg.se.muehle.model.gameFieldComponent.gamefield.*
import de.htwg.se.muehle.model.mechanicComponent.mechanic.*
import de.htwg.se.muehle.model.mechanicComponent.mechanicInterface
import de.htwg.se.muehle.model.{GameStateEnum, gameInterface}
import play.api.libs.json._


case class Game @Inject() (
                            mech: mechanicInterface,
                            field: gameFieldInterface,
                            message: Option[String] = None,
                            player: Stone = Stone.White,
                            currentGameState: GameStateEnum = GameStateEnum.SET_STONE
                          ) extends gameInterface {
  
  def this() = this(new Mechanic(), new Gamefield())
  def this(gamefield: gameFieldInterface) = this(Mechanic(), gamefield)


  override def getMechanic: mechanicInterface = mech

  override def getGameField: gameFieldInterface = field

  override def getMessage: Option[String] = message

  override def getPlayer: Stone = player

  override def getCurrentGameState: GameStateEnum = {
    if currentGameState == GameStateEnum.REMOVE_STONE then GameStateEnum.REMOVE_STONE else currentGameState
  }
  
  
  //-----------------------------------------------------
  //mechanic
  //-----------------------------------------------------

  def setStoneGame(ring: Int, posOnRing: Int): Game = {
    val gameState = checkAndSetGameState()
    if (gameState != GameStateEnum.SET_STONE) {
      return Game(mech, field, Some("Error! Aktuell darf kein Stein gesetzt werden, versuchen Sie einen anderen Befehl!"), player, gameState)
    }
  
    if (!mech.isSetLegal(field, ring, posOnRing)) {
      return Game(mech, field, Some("Error! Der Stein darf hier nicht Platziert werden!"), player, gameState)
    }
  
    val (newMech, newField) = mech.setStone(field, ring, posOnRing, PlayerState.stone)
    val currentPlayer: Stone = PlayerState.stone
  
    if (isMuehle(newField, ring, posOnRing)) {
      return Game(newMech, newField, Some(currentPlayer.toString + " hat eine Mühle! Bitte wählen Sie einen Stein den Sie entfernen möchten!"), currentPlayer, GameStateEnum.REMOVE_STONE)
    }
  
    PlayerState.next()
    Game(newMech, newField, Some(currentPlayer.toString + " hat einen Stein gesetzt!"), PlayerState.stone, gameState)
  }
  

  def moveStoneGame(oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Game = {
    val gameState = checkAndSetGameState()
    if (gameState != GameStateEnum.MOVE_STONE) {
      return Game(mech, field, Some("Error! Es darf aktuell kein Stein Bewegt werden!"), player, gameState)
    }
  
    if (!mech.isMoveLegal(field, oldRing, oldPosOnRing, newRing, newPosOnRing, PlayerState.stone)) {
      return Game(mech, field, Some("Error! Der Stein darf hier nicht bewegt werden!"), player, gameState)
    }
  
    val newField: gameFieldInterface = mech.moveStone(field, oldRing, oldPosOnRing, newRing, newPosOnRing, PlayerState.stone)
    val currentPlayer: Stone = PlayerState.stone
  
    if (isMuehle(newField, newRing, newPosOnRing)) {
      return Game(mech, newField, Some(currentPlayer.toString + " hat eine Mühle! Bitte wählen Sie einen Stein den Sie entfernen möchten!"), currentPlayer, GameStateEnum.REMOVE_STONE)
    }
  
    PlayerState.next()
    Game(mech, newField, Some(currentPlayer.toString + " hat einen Stein bewegt!"), PlayerState.stone, gameState)
  }

  def jumpStoneGame(oldRing: Int, oldPosOnRing: Int, newRing: Int, newPosOnRing: Int): Game = {
    val gameState = checkAndSetGameState()
    if (gameState != GameStateEnum.JUMP_STONE) {
      return Game(mech, field, Some("Error! Es darf aktuell nicht mit dem Stein gesprungen werden!"), player, gameState)
    }
  
    if (!mech.isJumpLegal(field.asInstanceOf[Gamefield], oldRing, oldPosOnRing, newRing, newPosOnRing, PlayerState.stone)) {
      return Game(mech, field, Some("Error! Mit dem Stein darf nicht gesprungen werden!"), player, gameState)
    }
  
    val newField: gameFieldInterface = mech.jumpStone(field.asInstanceOf[Gamefield], oldRing, oldPosOnRing, newRing, newPosOnRing, PlayerState.stone)
    val currentPlayer: Stone = PlayerState.stone
  
    if (isMuehle(newField, newRing, newPosOnRing)) {
      return Game(mech, newField, Some(PlayerState.stone.toString + " hat eine Mühle! Bitte wählen Sie einen Stein den Sie entfernen möchten!"), currentPlayer, GameStateEnum.REMOVE_STONE)
    }
  
    PlayerState.next()
    Game(mech, newField, Some(PlayerState.opponent.toString + " ist mit einem Stein gesprungen!"), currentPlayer, gameState)
  }

  def removeStoneGame(ring: Int, posOnRing: Int): Game = {
    if (currentGameState != GameStateEnum.REMOVE_STONE) {
      return Game(mech, field, Some("Error! Es gibt keine Mühle, es darf kein Stein entfernt werden!"), player, currentGameState)
    }
    val currentPlayer: Stone = PlayerState.stone
    if (!mech.isRemoveLegal(field, ring, posOnRing, currentPlayer)) {
      return Game(mech, field, Some("Error! Der Stein kann nicht entfernt werden!"), currentPlayer, currentGameState)
    }
    val newField: gameFieldInterface = mech.removeStone(field, ring, posOnRing, currentPlayer)
    PlayerState.next()
    val gameState = checkAndSetGameState()
    Game(mech, newField, Some(s"${currentPlayer} hat einen Stein entfernt!"), player, gameState)
  }

  def isMuehle(newField: gameFieldInterface, ring: Int, posOnRing: Int): Boolean = {
    mech.getEvaluateStrategy.checkForMuehle(newField, ring, posOnRing, PlayerState.stone)
  }
  
  
  //-----------------------------------------------------
  //gameField
  //-----------------------------------------------------

  private var useDecorator: Boolean = false

  def setDecorator(enabled: Boolean): Unit = {
    useDecorator = enabled
  }

  def getMesh: meshComponentInterface = {
    val baseMesh = ConcreteMesh(field.asInstanceOf[Gamefield])
    if (useDecorator) {
      ConcreteDecoratorMesh(baseMesh)
    } else {
      baseMesh
    }
  }
  
  //-----------------------------------------------------
  //game
  //-----------------------------------------------------

  def checkAndSetGameState(): GameStateEnum = {
    if (mech.getCounterOfSetStone < 18) { // 17, da die abfrage vor dem setzen des steins erfolgt //Note: muss noch überprüft werden
      GameStateEnum.SET_STONE
    } else if (mech.getCounterOfSetStone == 18 && field.getMuehleMatrix.flatten.count((stone:Stone) => stone == PlayerState.stone) > 3) {
      GameStateEnum.MOVE_STONE
    } else if (mech.getCounterOfSetStone == 18 && field.getMuehleMatrix.flatten.count((stone:Stone) => stone == PlayerState.stone) == 3) {
      GameStateEnum.JUMP_STONE
    } else {
      GameStateEnum.GAME_OVER
    }
  }

  def getOpponentPlayer: Stone = PlayerState.opponent
}


object PlayerState:
  private var currentStone: Stone = Stone.White
  def stone: Stone = currentStone
  def stone_=(newStone: Stone): Unit = currentStone = newStone
  def opponent: Stone = if stone.equals(Stone.White) then Stone.Black else Stone.White
  def next(): Unit = {
    currentStone = if (currentStone == Stone.White) Stone.Black else Stone.White
  }

//-----------------------------------------------------
// Json
//-----------------------------------------------------

object Game {
  implicit val writes: Writes[Game] = Writes {
    game => Json.obj(
      "mechanic" -> Json.toJson(game.mech)(mechanicInterface.writes),
      "field" -> Json.toJson(game.field)(gameFieldInterface.writes),
      "message" -> game.message,
      "player" -> Json.toJson(game.player),
      "currentGameState" -> Json.toJson(game.currentGameState)
    )
  }

  implicit val reads: Reads[Game] = Reads {
    json => for {
      mechanic <- (json \ "mechanic").validate[mechanicInterface](mechanicInterface.reads)
      field <- (json \ "field").validate[gameFieldInterface](gameFieldInterface.reads)
      message <- (json \ "message").validateOpt[String]
      player <- (json \ "player").validate[Stone]
      currentGameState <- (json \ "currentGameState").validate[GameStateEnum]
    } yield Game(mechanic, field, message, player, currentGameState)
  }
}