plugins {
    kotlin("jvm")
    kotlin("plugin.serialization")
    application
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
application {
    mainClass.set("dev.gradleviewer.MainKt")
    applicationName = "gradle-dependency-viewer"
}

dependencies {
    implementation(project(":core"))
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.10.0")
    val ktor = "3.5.1"
    implementation("io.ktor:ktor-server-cio:$ktor")
    implementation("io.ktor:ktor-server-content-negotiation:$ktor")
    implementation("io.ktor:ktor-serialization-kotlinx-json:$ktor")
    implementation("io.ktor:ktor-server-status-pages:$ktor")
    runtimeOnly("ch.qos.logback:logback-classic:1.5.32")
    testImplementation("io.ktor:ktor-server-test-host:$ktor")
    testImplementation(kotlin("test-junit"))
}

sourceSets.main {
    resources.srcDir(rootProject.file("app"))
    resources.include("static/**", "templates/**", "viz/**", "logback.xml")
}

tasks.processResources {
    val samples = rootProject.fileTree("app/static/sample") { include("*.json") }
    inputs.files(samples)
    doLast {
        destinationDir.resolve("sample-index.txt").writeText(samples.files.sortedBy { it.name }.joinToString("\n") { it.name })
    }
}
