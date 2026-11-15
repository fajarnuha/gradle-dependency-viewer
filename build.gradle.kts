import java.io.ByteArrayOutputStream
import java.math.BigInteger.ONE
import javax.inject.Inject
import org.gradle.api.tasks.options.Option
import org.gradle.process.ExecOperations

plugins {
    kotlin("multiplatform") version "2.3.21" apply false
    kotlin("jvm") version "2.3.21" apply false
    kotlin("plugin.serialization") version "2.3.21" apply false
    id("com.vanniktech.maven.publish") version "0.37.0" apply false
}

allprojects { version = providers.gradleProperty("version").get() }

subprojects {
    pluginManager.withPlugin("com.vanniktech.maven.publish") {
        group = "com.fajarnuha"
        val projectName = if (name == "core") "Gradle Dependency Viewer Core" else "Gradle Dependency Viewer Plugin"
        val projectDescription = if (name == "core") {
            "Shared dependency graph model and serialization for Gradle Dependency Viewer."
        } else {
            "Gradle plugin that exports resolved dependency graphs as JSON."
        }
        val repositoryUrl = "https://github.com/fajarnuha/gradle-dependency-viewer"
        extensions.configure<com.vanniktech.maven.publish.MavenPublishBaseExtension> {
            publishToMavenCentral()
            if (providers.gradleProperty("signingInMemoryKey").isPresent) {
                signAllPublications()
            }
            pom {
                name.set(projectName)
                description.set(projectDescription)
                url.set(repositoryUrl)
                licenses {
                    license {
                        name.set("MIT License")
                        url.set("$repositoryUrl/blob/main/LICENSE")
                    }
                }
                developers {
                    developer {
                        id.set("fajarnuha")
                        name.set("Fajar Ulin Nuha")
                        url.set("https://fajarnuha.com")
                    }
                }
                scm {
                    url.set(repositoryUrl)
                    connection.set("scm:git:$repositoryUrl.git")
                    developerConnection.set("scm:git:ssh://git@github.com/fajarnuha/gradle-dependency-viewer.git")
                }
            }
        }
    }
}

abstract class BumpVersion @Inject constructor(private val execOperations: ExecOperations) : DefaultTask() {
    enum class Bump { MAJOR, MINOR, PATCH }

    @get:Input
    @set:Option(option = "bump", description = "Version component to increment (default: minor).")
    var bump: Bump = Bump.MINOR

    @get:Internal
    abstract val repositoryDir: DirectoryProperty

    @TaskAction
    fun release() {
        val status = ByteArrayOutputStream()
        execOperations.exec {
            workingDir(repositoryDir.get().asFile)
            commandLine("git", "status", "--porcelain=v1", "--untracked-files=all")
            standardOutput = status
        }
        if (status.size() != 0) {
            throw GradleException("Commit or stash all Git changes before bumping the version.\n$status")
        }

        val properties = repositoryDir.file("gradle.properties").get().asFile
        val content = properties.readText()
        val versionPattern = Regex("""^version=([0-9]+)\.([0-9]+)\.([0-9]+)$""", RegexOption.MULTILINE)
        val current = versionPattern.findAll(content).singleOrNull()
            ?: throw GradleException("Expected one version in major.minor.patch format in gradle.properties.")
        val (major, minor, patch) = current.groupValues.drop(1).map { it.toBigInteger() }
        val next = when (bump) {
            Bump.MAJOR -> "${major + ONE}.0.0"
            Bump.MINOR -> "$major.${minor + ONE}.0"
            Bump.PATCH -> "$major.$minor.${patch + ONE}"
        }
        val tag = "v$next"

        properties.writeText(content.replaceRange(current.range, "version=$next"))
        git("add", "--", properties.name)
        git("commit", "-m", "Bump version to $tag")
        git("tag", tag)
        git("push")
        git("push", "origin", tag)
    }

    private fun git(vararg args: String) {
        execOperations.exec {
            workingDir(repositoryDir.get().asFile)
            commandLine("git", *args)
        }
    }
}

tasks.register<BumpVersion>("bumpVersion") {
    group = "release"
    description = "Compile the server, bump the version, and push the release commit and tag."
    repositoryDir.set(layout.projectDirectory)
    dependsOn(":server:classes")
}
