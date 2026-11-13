package com.fajarnuha.dependency_graph

import dev.gradleviewer.DependencyGraphReport
import dev.gradleviewer.GraphEdge
import dev.gradleviewer.GraphNode
import org.gradle.api.DefaultTask
import org.gradle.api.GradleException
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.artifacts.component.ProjectComponentIdentifier
import org.gradle.api.artifacts.result.ResolvedComponentResult
import org.gradle.api.artifacts.result.ResolvedDependencyResult
import org.gradle.api.artifacts.result.ResolvedVariantResult
import org.gradle.api.artifacts.result.UnresolvedDependencyResult
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.Internal
import org.gradle.api.tasks.OutputFile
import org.gradle.api.tasks.TaskAction
import org.gradle.work.DisableCachingByDefault
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.HexFormat

class DependencyGraphPlugin : Plugin<Project> {
    override fun apply(project: Project) {
        val configurationName = project.providers.gradleProperty("dependencyGraphConfiguration").orElse("runtimeClasspath")
        project.tasks.register("exportDependencyGraph", ExportDependencyGraph::class.java) { task ->
            val name = configurationName.get()
            val resolution = project.providers.provider {
                val configuration = project.configurations.findByName(name)
                    ?: throw GradleException("Configuration '$name' does not exist in ${project.path}")
                if (!configuration.isCanBeResolved) {
                    throw GradleException("Configuration '$name' in ${project.path} cannot be resolved")
                }
                configuration.incoming.resolutionResult
            }
            task.group = "reporting"
            task.description = "Export one resolved dependency graph as JSON."
            task.projectPath.set(project.path)
            task.configurationName.set(name)
            task.rootComponent.set(resolution.flatMap { it.rootComponent })
            task.rootVariant.set(resolution.flatMap { it.rootVariant })
            task.reportFile.set(project.layout.buildDirectory.file("reports/dependency-graph/$name.json"))
        }
    }
}

@DisableCachingByDefault(because = "The graph is resolved again for each invocation")
abstract class ExportDependencyGraph : DefaultTask() {
    init {
        doNotTrackState("The resolved dependency graph can change independently of declared dependencies.")
    }

    @get:Input abstract val projectPath: Property<String>
    @get:Input abstract val configurationName: Property<String>
    @get:Internal abstract val rootComponent: Property<ResolvedComponentResult>
    @get:Internal abstract val rootVariant: Property<ResolvedVariantResult>
    @get:OutputFile abstract val reportFile: RegularFileProperty

    @TaskAction
    fun export() {
        val report = resolveGraph(rootComponent.get(), rootVariant.get(), projectPath.get(), configurationName.get())
        val json = report.toJson().toString() + "\n"
        val destination = reportFile.get().asFile.toPath()
        Files.createDirectories(destination.parent)
        val temporary = Files.createTempFile(destination.parent, ".dependency-graph-", ".tmp")
        try {
            Files.writeString(temporary, json)
            Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        } finally {
            Files.deleteIfExists(temporary)
        }
        logger.lifecycle("Dependency graph written to ${reportFile.get().asFile}")
    }
}

private fun resolveGraph(
    root: ResolvedComponentResult,
    rootVariant: ResolvedVariantResult,
    projectPath: String,
    configuration: String,
): DependencyGraphReport {
    val rootId = "root:"
    val rootLabel = "project $projectPath"
    val nodes = mutableListOf(GraphNode(rootId, rootLabel, "", "", rootLabel))
    val edges = mutableListOf<GraphEdge>()
    val variants = mutableMapOf(rootVariant to rootId)
    val pending = ArrayDeque(listOf(root to rootVariant))
    while (pending.isNotEmpty()) {
        val (component, variant) = pending.removeFirst()
        for (dependency in component.getDependenciesForVariant(variant)) {
            when (dependency) {
                is UnresolvedDependencyResult -> throw GradleException(
                    "Could not resolve ${dependency.requested.displayName} in $projectPath ($configuration):" +
                        "\n${dependency.failure.message}",
                )
                is ResolvedDependencyResult -> {
                    val selected = dependency.resolvedVariant
                    val target = variants.getOrPut(selected) {
                        val node = selected.toGraphNode()
                        nodes.add(node)
                        pending.addLast(dependency.selected to selected)
                        node.id
                    }
                    edges.add(GraphEdge(variants.getValue(variant), target, dependency.requested.displayName, dependency.isConstraint))
                }
                else -> error("Unsupported dependency result: ${dependency.javaClass.name}")
            }
        }
    }
    return DependencyGraphReport(
        schemaVersion = 1,
        projectPath = projectPath,
        configuration = configuration,
        rootId = rootId,
        nodes = nodes.sortedBy { it.id },
        edges = edges.sortedWith(compareBy(GraphEdge::source, GraphEdge::target, GraphEdge::requested, GraphEdge::constraint)),
    )
}

private fun ResolvedVariantResult.toGraphNode(): GraphNode {
    val (module, version) = when (val owner = owner) {
        is ModuleComponentIdentifier -> "${owner.group}:${owner.module}" to owner.version
        is ProjectComponentIdentifier -> "project ${owner.buildTreePath}" to ""
        else -> owner.displayName to ""
    }
    val full = if (version.isEmpty()) module else "$module:$version"
    val attributeKeys = attributes.keySet().sortedBy { it.name }
    val idParts = listOf(full, displayName, attributeKeys.size.toString()) +
        attributeKeys.flatMap { listOf(it.name, attributes.getAttribute(it).toString()) } +
        capabilities.sortedWith(compareBy({ it.group }, { it.name }, { it.version })).flatMap {
            listOf(it.group, it.name, it.version.orEmpty())
        }
    val identity = idParts.joinToString("") { "${it.length}:$it" }
    val id = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(identity.encodeToByteArray()))
    return GraphNode(id, module, version, "", full)
}
