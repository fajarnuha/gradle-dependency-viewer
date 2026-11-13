plugins {
    kotlin("jvm")
    `java-gradle-plugin`
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

gradlePlugin {
    plugins {
        register("dependencyGraph") {
            id = "com.fajarnuha.dependency-graph"
            implementationClass = "com.fajarnuha.dependency_graph.DependencyGraphPlugin"
        }
    }
}

dependencies {
    implementation(project(":core"))
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.10.0")
    testImplementation(gradleTestKit())
    testImplementation(kotlin("test-junit"))
}
