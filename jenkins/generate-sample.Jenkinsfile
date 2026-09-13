// Generates a pre-compiled dependency sample from a public GitHub Android repository and opens a
// pull request that adds it to app/static/sample/.
//
// Job setup: a Pipeline job ("Pipeline script from SCM") on this repository with the script path
// jenkins/generate-sample.Jenkinsfile. The agent needs git, curl, unzip and python3. Gradle runs in
// ANDROID_IMAGE through the Docker Pipeline plugin; leave ANDROID_IMAGE blank to run it on the agent,
// which then needs a JDK and the Android SDK. GITHUB_CREDENTIALS_ID names a "Username with password"
// credential whose password is a GitHub token that can push branches to and open pull requests on
// VIEWER_REPO.
//
// The downloaded project's Gradle build is untrusted code: it runs in the container, and no
// credential is bound while it runs.

pipeline {
    agent any

    options {
        timeout(time: 90, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        string(name: 'REPO_URL', defaultValue: '', trim: true,
            description: 'Public GitHub repository of an Android app, e.g. https://github.com/android/architecture-samples')
        string(name: 'GIT_REF', defaultValue: 'HEAD', trim: true,
            description: 'Branch, tag or commit to use. HEAD is the default branch.')
        string(name: 'SAMPLE_NAME', defaultValue: '', trim: true,
            description: 'Name shown on the home page. Defaults to the repository name.')
        string(name: 'MODULE', defaultValue: '', trim: true,
            description: 'Gradle path of the app module, e.g. :app. Detected when blank.')
        string(name: 'CONFIGURATION', defaultValue: '', trim: true,
            description: 'Configuration to dump, e.g. releaseRuntimeClasspath. When blank, the shortest release runtime classpath is used.')
        // Multi-arch (amd64 and arm64). Dumping dependencies needs no Android SDK with recent Android
        // Gradle plugins, so a plain JDK image such as eclipse-temurin:17-jdk also works and is smaller.
        string(name: 'ANDROID_IMAGE', defaultValue: 'ghcr.io/cirruslabs/android-sdk:35', trim: true,
            description: 'Docker image with a JDK (and the Android SDK) that Gradle runs in. Blank runs Gradle on the agent.')
        string(name: 'BASE_BRANCH', defaultValue: 'main', trim: true,
            description: 'Branch of the viewer repository the pull request targets.')
        booleanParam(name: 'DRY_RUN', defaultValue: false,
            description: 'Only generate and archive the sample JSON; do not open a pull request.')
    }

    environment {
        VIEWER_REPO = 'fajarnuha/gradle-dependency-viewer'
        GITHUB_CREDENTIALS_ID = 'github-token'
        SAMPLE_DIR = 'app/static/sample'
        GIT_BOT_NAME = 'gradle-dependency-viewer bot'
        GIT_BOT_EMAIL = 'gradle-dependency-viewer-bot@users.noreply.github.com'
        GRADLE_ARGS = '--no-daemon --console=plain'
    }

    stages {
        stage('Download') {
            steps {
                script {
                    // Outside the checkout, so nothing downloaded can end up in the pull request.
                    env.WORK_DIR = "${env.WORKSPACE}@tmp/generate-sample"
                    exportEnv(sh(returnStdout: true, script: '''
                        python3 jenkins/generate_sample.py repo-info "$REPO_URL" --ref "$GIT_REF" --name "$SAMPLE_NAME"
                    '''))
                }
                sh '''
                    rm -rf "$WORK_DIR"
                    mkdir -p "$WORK_DIR/src"
                    curl -fsSL --retry 3 -o "$WORK_DIR/source.zip" \
                        "https://github.com/$REPO_OWNER/$REPO_NAME/archive/$REPO_SHA.zip"
                    unzip -q "$WORK_DIR/source.zip" -d "$WORK_DIR/src"
                    rm -f "$WORK_DIR/source.zip"
                '''
            }
        }

        stage('Validate Android project') {
            steps {
                script {
                    exportEnv(sh(returnStdout: true, script: '''
                        python3 jenkins/generate_sample.py validate "$WORK_DIR/src" --module "$MODULE"
                    '''))
                }
            }
        }

        stage('Dump dependencies') {
            steps {
                script {
                    inAndroidEnv {
                        // Lists the module's runtime classpath configurations without resolving them.
                        sh '''
                            cd "$PROJECT_DIR"
                            chmod +x gradlew
                            ./gradlew $GRADLE_ARGS --no-configure-on-demand --no-configuration-cache \
                                --init-script "$WORKSPACE/jenkins/list-configurations.init.gradle" \
                                "$GRADLE_MODULE_SELECTOR" help > "$WORK_DIR/configurations.txt"
                        '''
                    }
                    exportEnv(sh(returnStdout: true, script: '''
                        python3 jenkins/generate_sample.py pick-config --configuration "$CONFIGURATION" \
                            < "$WORK_DIR/configurations.txt"
                    '''))
                    inAndroidEnv {
                        sh '''
                            cd "$PROJECT_DIR"
                            if [ "$GRADLE_MODULE" = ":" ]; then TASK=":dependencies"; else TASK="$GRADLE_MODULE:dependencies"; fi
                            ./gradlew $GRADLE_ARGS "$TASK" --configuration "$GRADLE_CONFIGURATION" \
                                > "$WORK_DIR/dependencies.txt"
                        '''
                    }
                }
            }
        }

        stage('Convert') {
            steps {
                script {
                    exportEnv(sh(returnStdout: true, script: '''
                        python3 jenkins/generate_sample.py convert "$WORK_DIR/dependencies.txt" \
                            --name "$SAMPLE_SLUG" --out-dir "$SAMPLE_DIR"
                    '''))
                    currentBuild.description = "${env.SAMPLE_SLUG}: ${env.GRADLE_MODULE} ${env.GRADLE_CONFIGURATION}"
                }
                archiveArtifacts artifacts: "${env.SAMPLE_DIR}/${env.SAMPLE_FILE}"
            }
        }

        stage('Open pull request') {
            when {
                expression { !params.DRY_RUN }
            }
            steps {
                script {
                    env.PR_BRANCH = "sample/${env.SAMPLE_SLUG}-${env.BUILD_NUMBER}"
                }
                withCredentials([usernamePassword(credentialsId: env.GITHUB_CREDENTIALS_ID,
                        usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                    // The credential helper reads the token from the environment, so it never appears
                    // in a command line or URL.
                    sh '''
                        AUTH='credential.helper=!f() { echo "username=$GH_USER"; echo "password=$GH_TOKEN"; }; f'
                        git -c credential.helper= -c "$AUTH" fetch --no-tags \
                            "https://github.com/$VIEWER_REPO.git" "$BASE_BRANCH"
                        git checkout -B "$PR_BRANCH" FETCH_HEAD
                        git add -A "$SAMPLE_DIR"
                        git -c user.name="$GIT_BOT_NAME" -c user.email="$GIT_BOT_EMAIL" commit -q \
                            -m "Add $SAMPLE_SLUG dependency sample" \
                            -m "Generated from https://github.com/$REPO_OWNER/$REPO_NAME at $REPO_SHA ($GRADLE_MODULE, $GRADLE_CONFIGURATION)."
                        git -c credential.helper= -c "$AUTH" push \
                            "https://github.com/$VIEWER_REPO.git" "HEAD:refs/heads/$PR_BRANCH"
                    '''
                    script {
                        exportEnv(sh(returnStdout: true, script: '''
                            python3 jenkins/generate_sample.py open-pr --repo "$VIEWER_REPO" \
                                --branch "$PR_BRANCH" --base "$BASE_BRANCH" \
                                --sample "$SAMPLE_DIR/$SAMPLE_FILE" \
                                --source "https://github.com/$REPO_OWNER/$REPO_NAME" --sha "$REPO_SHA" \
                                --module "$GRADLE_MODULE" --configuration "$GRADLE_CONFIGURATION" \
                                --replaces "$REPLACED_SAMPLES"
                        '''))
                        currentBuild.description = "${env.SAMPLE_SLUG}: ${env.PR_URL}"
                    }
                }
            }
        }
    }

    post {
        always {
            // Remove the downloaded project, its Gradle caches and the generated sample, so the next
            // build starts from a clean checkout.
            script {
                if (env.WORK_DIR) {
                    dir(env.WORK_DIR) {
                        deleteDir()
                    }
                }
            }
            deleteDir()
        }
    }
}

// Exports the KEY=value lines a helper printed to stdout as environment variables.
def exportEnv(String output) {
    for (String line : output.readLines()) {
        int separator = line.indexOf('=')
        if (separator > 0) {
            env."${line.substring(0, separator).trim()}" = line.substring(separator + 1).trim()
        }
    }
}

// Runs Gradle steps in ANDROID_IMAGE (or on the agent when it is blank), with every home directory
// inside WORK_DIR so that the cleanup removes the Gradle and Android caches too.
def inAndroidEnv(Closure body) {
    withEnv([
        "HOME=${env.WORK_DIR}/home",
        "GRADLE_USER_HOME=${env.WORK_DIR}/gradle-home",
        "ANDROID_USER_HOME=${env.WORK_DIR}/android-home",
    ]) {
        if (params.ANDROID_IMAGE) {
            docker.image(params.ANDROID_IMAGE).inside {
                body()
            }
        } else {
            body()
        }
    }
}
