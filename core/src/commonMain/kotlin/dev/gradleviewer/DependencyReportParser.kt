package dev.gradleviewer

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.put

@Serializable
private data class ParsedNode(
    val module: String,
    val version: String,
    val resolution: String,
    val full: String,
    val children: MutableList<ParsedNode> = mutableListOf(),
)

/** Gradle's tree markers use five columns per level. Repeated sections share one root list. */
fun parseDependencies(text: String): JsonObject {
    val lines = text.lineSequence().toList()
    val project = lines.firstNotNullOfOrNull {
        Regex("^Project ':([^']+)'").find(it.trim())?.groupValues?.get(1)
    } ?: "root"
    val roots = mutableListOf<ParsedNode>()
    val stack = mutableListOf<Pair<ParsedNode, Int>>()
    var parsing = false
    for (line in lines) {
        if (Regex("^\\w+(Runtime|Compile)Classpath").containsMatchIn(line)) {
            parsing = true
            continue
        }
        if (!parsing) continue
        val full = Regex("--- (.*)").find(line)?.groupValues?.get(1)?.trim() ?: continue
        val level = line.indexOfFirst { it !in " |\\+-" }.let { if (it < 0) 0 else it / 5 }
        val parts = full.substringBefore(" -> ").split(':')
        val isProject = full.startsWith("project ")
        val module = when {
            isProject -> full.replace(Regex("\\s*\\(\\*\\)\\s*$"), "")
            parts.size > 2 -> parts.take(2).joinToString(":")
            " -> " in full -> full.substringBefore(" -> ")
            else -> full
        }
        val versionPart = when {
            isProject -> ""
            " -> " in full -> full.substringAfter(" -> ").substringBefore(" -> ")
            parts.size > 2 -> parts[2]
            else -> ""
        }
        val version = Regex("[\\d.\\-a-zA-Z]+").find(versionPart)?.value.orEmpty()
        val resolution = Regex("\\(([*+c])\\)").find(full)?.groupValues?.get(1).orEmpty()
        val node = ParsedNode(module, version, resolution, full)
        while (stack.isNotEmpty() && stack.last().second >= level) stack.removeAt(stack.lastIndex)
        if (stack.isEmpty()) roots.add(node) else stack.last().first.children.add(node)
        stack.add(node to level)
    }
    return buildJsonObject { put(project, dependencyJson.encodeToJsonElement(roots)) }
}
