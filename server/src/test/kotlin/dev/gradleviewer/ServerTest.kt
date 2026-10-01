package dev.gradleviewer

import io.ktor.client.request.*
import io.ktor.client.request.forms.*
import io.ktor.client.statement.*
import io.ktor.http.*
import io.ktor.server.testing.*
import kotlinx.serialization.json.*
import kotlin.test.*

class ServerTest {
    @Test fun apiAndBundledSampleContracts() = testApplication {
        application { viewerModule() }
        val index = client.get("/")
        assertEquals(HttpStatusCode.OK, index.status)
        assertTrue(index.bodyAsText().contains("Pre-Compiled Open Source Projects"))
        assertTrue(Regex("/static/app.js\\?v=[a-f0-9]{10}").containsMatchIn(index.bodyAsText()))
        assertEquals("ok", client.get("/healthz").bodyAsText())
        assertEquals(HttpStatusCode.NotFound, client.get("/api/files").status)
        val samples = dependencyJson.parseToJsonElement(client.get("/api/samples").bodyAsText()).jsonArray
        assertTrue(samples.isNotEmpty())
        for (sample in samples) {
            val filename = sample.jsonObject["filename"]!!.jsonPrimitive.content
            val raw = client.get(sample.jsonObject["path"]!!.jsonPrimitive.content)
            assertEquals(HttpStatusCode.OK, raw.status)
            val data = dependencyJson.parseToJsonElement(raw.bodyAsText()).jsonObject
            val report = data["raw_txt"]!!.jsonPrimitive.content
            val expectedTree = treeView(data)
            assertEquals(expectedTree, parseDependencies(report), filename)
            val upload = client.post("/api/upload") {
                setBody(MultiPartFormDataContent(formData {
                    append("file", report.encodeToByteArray(), Headers.build {
                        append(HttpHeaders.ContentDisposition, "filename=\"my_app.txt\"")
                        append(HttpHeaders.ContentType, "text/plain")
                    })
                }))
            }
            assertEquals(HttpStatusCode.OK, upload.status)
            val uploaded = dependencyJson.parseToJsonElement(upload.bodyAsText()).jsonObject
            assertEquals("my_app", uploaded["name"]!!.jsonPrimitive.content)
            assertEquals(expectedTree, uploaded["json"])
            for (endpoint in listOf("tree", "graph", "enlist")) {
                val response = client.post("/api/$endpoint") {
                    contentType(ContentType.Application.Json)
                    setBody(buildJsonObject { put("data", data) }.toString())
                }
                assertEquals(HttpStatusCode.OK, response.status, endpoint)
                when (endpoint) {
                    "tree" -> assertEquals(expectedTree, dependencyJson.parseToJsonElement(response.bodyAsText()))
                    "graph" -> assertTrue(dependencyJson.parseToJsonElement(response.bodyAsText()).jsonObject["nodes"]!!.jsonArray.size > 100)
                    "enlist" -> assertEquals(enlistYaml(data), response.bodyAsText())
                }
            }
            for (viewer in listOf("graph", "tree")) {
                val page = client.get("/viz/${viewer}_viewer.html?sample=$filename").bodyAsText()
                assertFalse(page.contains("__VIEW_DATA__"))
                assertFalse(page.contains("__FILE_NAME__"))
                assertTrue(page.contains(filename))
                if (viewer == "tree") assertFalse(page.contains("\"raw_txt\":"))
            }
        }
    }

    @Test fun invalidRequestsAndEscaping() = testApplication {
        application { viewerModule() }
        val badData = client.post("/api/graph") {
            contentType(ContentType.Application.Json)
            setBody("{\"data\":{\"root\":[1]}}")
        }
        assertEquals(HttpStatusCode.BadRequest, badData.status)
        assertTrue(badData.bodyAsText().contains("detail"))
        val missingData = client.post("/api/tree") {
            contentType(ContentType.Application.Json); setBody("{}")
        }
        assertEquals(HttpStatusCode.BadRequest, missingData.status)
        val page = client.get("/viz/graph_viewer.html?sample=../main.py").bodyAsText()
        assertTrue(page.contains("const serverGraphData = null"))
        val xss = client.get("/viz/tree_viewer.html?sample=%3Cscript%3Ealert(1)%3C%2Fscript%3E").bodyAsText()
        assertTrue(xss.contains("&lt;script&gt;alert(1)&lt;/script&gt;"))
        assertFalse(inlineJson(JsonPrimitive("</script>\u2028")).contains("</script>"))
        val upload = client.post("/api/upload") {
            setBody(MultiPartFormDataContent(formData {
                append("file", "not a report".encodeToByteArray(), Headers.build {
                    append(HttpHeaders.ContentDisposition, "filename=\"report.json\"")
                })
            }))
        }
        assertEquals(HttpStatusCode.BadRequest, upload.status)
        assertEquals("Only .txt files are supported.", dependencyJson.parseToJsonElement(upload.bodyAsText()).jsonObject["detail"]!!.jsonPrimitive.content)
    }

    @Test fun supportedEncodings() {
        val report = "Project ':café'\ndebugRuntimeClasspath\n+--- org.example:a:1\n"
        for (encoding in listOf("UTF-8", "UTF-16", "windows-1252")) {
            assertEquals(report, decodeReport(report.toByteArray(charset(encoding))), encoding)
        }
        assertEquals(report, decodeReport(byteArrayOf(0xef.toByte(), 0xbb.toByte(), 0xbf.toByte()) + report.encodeToByteArray()))
    }
}
