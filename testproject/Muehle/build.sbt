val scala3Version = "3.5.1"

lazy val root = project
  .in(file("."))
  .settings(
    name := "muehle",
    version := "0.1.0-SNAPSHOT",

    scalaVersion := scala3Version,

    libraryDependencies ++= Seq(
      "org.scalactic" %% "scalactic" % "3.2.18",
      "org.scalatest" %% "scalatest" % "3.2.18" % "test",
      "org.scala-lang.modules" %% "scala-swing" % "3.0.0",
      "net.codingwell" %% "scala-guice" % "7.0.0",
      "com.typesafe.play" %% "play-json" % "2.10.3",
      "org.scala-lang.modules" %% "scala-xml" % "2.2.0"
    )
  )
