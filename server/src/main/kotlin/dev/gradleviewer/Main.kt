package dev.gradleviewer

import io.ktor.http.*
import io.ktor.http.content.*
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*
import io.ktor.server.http.content.*
import io.ktor.server.plugins.*
import io.ktor.server.plugins.contentnegotiation.*
import io.ktor.server.plugins.statuspages.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import io.ktor.serialization.kotlinx.json.*
import io.ktor.utils.io.*
import kotlinx.io.readByteArray
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import java.nio.ByteBuffer
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest
import java.io.File

@Serializable
data class ViewRequest(val data: JsonObject, val filter: String? = null, val project_only: Boolean = false)

private fun resource(path: String): ByteArray = checkNotNull(
    ViewRequest::class.java.classLoader.getResourceAsStream(path)
) { "Missing resource: $path" }.use { it.readBytes() }

/** Decode once for both the preview and parser, including Windows and BOM-marked reports. */
fun decodeReport(bytes: ByteArray): String {
    val encoding = when {
        bytes.size >= 2 && ((bytes[0] == 0xff.toByte() && bytes[1] == 0xfe.toByte()) ||
            (bytes[0] == 0xfe.toByte() && bytes[1] == 0xff.toByte())) -> "UTF-16"
        else -> "UTF-8"
    }
    return try {
        Charset.forName(encoding).newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString().removePrefix("\uFEFF")
    } catch (_: java.nio.charset.CharacterCodingException) {
        String(bytes, Charset.forName("windows-1252"))
    }
}

// Escape the script context as well as JSON strings, so report text cannot close a script tag.
fun inlineJson(value: JsonElement?): String = (value ?: JsonNull).toString()
    .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    .replace("'", "\\u0027").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

private fun htmlText(value: String) = value.replace("&", "&amp;").replace("<", "&lt;")
    .replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&#39;")

fun Application.viewerModule() {
    install(ContentNegotiation) { json(dependencyJson) }
    install(StatusPages) {
        exception<BadRequestException> { call, cause ->
            call.respond(HttpStatusCode.BadRequest, buildJsonObject { put("detail", cause.message ?: "Invalid request body.") })
        }
        exception<IllegalArgumentException> { call, cause ->
            call.respond(HttpStatusCode.BadRequest, buildJsonObject { put("detail", "Invalid dependency data: ${cause.message}") })
        }
        exception<Throwable> { call, cause ->
            if (cause is java.util.concurrent.CancellationException) throw cause
            call.application.log.error("Request failed", cause)
            call.respond(HttpStatusCode.InternalServerError, buildJsonObject { put("detail", "Internal server error.") })
        }
    }
    val filenames = resource("sample-index.txt").decodeToString().lineSequence().filter { it.isNotBlank() }.toList()
    val samples = filenames.associateWith { dependencyJson.parseToJsonElement(resource("static/sample/$it").decodeToString()).jsonObject }
    val summaries = JsonArray(samples.map { (filename, data) ->
        buildJsonObject {
            put("name", filename.substringBefore('_'))
            put("filename", filename)
            put("path", "/static/sample/$filename")
            sampleSummary(data).forEach { (key, value) -> put(key, value) }
        }
    })
    var index = resource("templates/index.html").decodeToString()
    for ((marker, path) in mapOf("__APP_CSS__" to "app.css", "__APP_JS__" to "app.js")) {
        val hash = MessageDigest.getInstance("SHA-256").digest(resource("static/$path"))
            .joinToString("") { "%02x".format(it) }.take(10)
        index = index.replace(marker, "/static/$path?v=$hash")
    }
    val viewerPages = listOf("graph", "tree").associateWith { resource("viz/${it}_viewer.html").decodeToString() }
    routing {
        get("/healthz") { call.respondText("ok") }
        get("/") { call.respondText(index, ContentType.Text.Html) }
        get("/api/samples") { call.respond(summaries) }
        for (viewer in viewerPages.keys) {
            get("/viz/${viewer}_viewer.html") {
                val filename = call.request.queryParameters["sample"]
                val data = samples[filename]?.let {
                    val filtered = filterDependencies(it, call.request.queryParameters["filter"],
                        call.request.queryParameters["project_only"]?.lowercase() in setOf("true", "1", "yes", "on"))
                    if (viewer == "graph") toGraph(filtered) else treeView(filtered)
                }
                val values = mapOf("__VIEW_DATA__" to inlineJson(data),
                    "__FILE_NAME__" to htmlText(filename?.takeIf { it.isNotEmpty() } ?: "Sample data"))
                val page = Regex("__VIEW_DATA__|__FILE_NAME__").replace(viewerPages.getValue(viewer)) { values.getValue(it.value) }
                call.respondText(page, ContentType.Text.Html)
            }
        }
        staticResources("/static", "static")
        post("/api/upload") {
            var result: JsonObject? = null
            call.receiveMultipart().forEachPart { part ->
                try {
                    if (part is PartData.FileItem && part.name == "file") {
                        val filename = part.originalFileName.orEmpty()
                        if (filename.isBlank()) throw BadRequestException("No file uploaded.")
                        if (!filename.endsWith(".txt", ignoreCase = true)) throw BadRequestException("Only .txt files are supported.")
                        val text = decodeReport(part.provider().readRemaining().readByteArray())
                        result = buildJsonObject {
                            put("name", filename.substringAfterLast('/').substringAfterLast('\\').dropLast(4))
                            put("txt", text)
                            put("json", parseDependencies(text))
                        }
                    }
                } finally { part.release() }
            }
            call.respond(result ?: throw BadRequestException("No file uploaded."))
        }
        post("/api/graph") {
            val request = call.receive<ViewRequest>()
            call.respond(toGraph(filterDependencies(request.data, request.filter, request.project_only)))
        }
        post("/api/tree") {
            val request = call.receive<ViewRequest>()
            call.respond(treeView(filterDependencies(request.data, request.filter, request.project_only)))
        }
        post("/api/enlist") {
            val request = call.receive<ViewRequest>()
            call.respondText(enlistYaml(request.data), ContentType.parse("application/x-yaml"))
        }
    }
}

fun main(args: Array<String>) {
    if (args.isNotEmpty()) {
        runCli(args)
        return
    }
    val port = System.getenv("PORT")?.toInt() ?: 8000
    embeddedServer(CIO, port = port, host = System.getenv("HOST") ?: "0.0.0.0") {
        viewerModule()
    }.start(wait = true)
}

/** The installed distribution is also the CLI used by Jenkins; diagnostics stay on stderr. */
private fun runCli(args: Array<String>) {
    require(args.size >= 2) { "Usage: gradle-dependency-viewer <parse|graph|tree|enlist|summary> FILE [options]" }
    val command = args[0]
    val file = File(args[1])
    fun option(name: String): String? = args.indexOf(name).takeIf { it >= 0 }?.let {
        require(it + 1 < args.size) { "Missing value for $name" }
        args[it + 1]
    }
    val output = if (command == "parse") {
        parseDependencies(decodeReport(file.readBytes())).toString()
    } else {
        val data = dependencyJson.parseToJsonElement(file.readText()).jsonObject
        when (command) {
            "graph" -> toGraph(data, option("--distance")?.toInt(), option("--exclude")).toString()
            "tree" -> filterDependencies(data, option("--filter"), "--project-only" in args).toString()
            "enlist" -> enlistYaml(data)
            "summary" -> sampleSummary(data).toString()
            else -> error("Unknown command: $command")
        }
    }
    val destination = option("--output")
    if (destination == null) println(output) else File(destination).writeText(output)
}
