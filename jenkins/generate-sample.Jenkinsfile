// Generates a pre-compiled dependency sample from a public GitHub Android repository and opens a
// pull request that adds it to app/static/sample/.
//
// Job setup: a Pipeline job ("Pipeline script from SCM") on this repository with the script path
// jenkins/generate-sample.Jenkinsfile. It runs on the agent labelled "self" (an x86 machine), which
// needs git, curl, unzip, python3 and a JDK (17 or newer; the Android SDK is optional, since dumping
// dependencies needs none with recent Android Gradle plugins). Gradle runs directly on the agent, no
// Docker. GITHUB_CREDENTIALS_ID names a "Username with password" credential whose password is a
// GitHub token that can push branches to and open pull requests on VIEWER_REPO.
//
// Caches: with CACHE_GRADLE on, Gradle's downloads (wrapper distributions, dependencies) stay in
// GRADLE_CACHE_DIR on the agent; everything else a build downloads is deleted when it ends.
//
// The downloaded project's Gradle build is untrusted code: it runs on the agent as the Jenkins user,
// with HOME pointed at a throwaway directory, and no credential is bound while it runs.

pipeline {
    agent { label 'self' }

    options {
        timeout(time: 90, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        // Builds share the Gradle cache, so run one build at a time.
        disableConcurrentBuilds()
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
        booleanParam(name: 'CACHE_GRADLE', defaultValue: true,
            description: "Keep Gradle's downloads on the agent between builds. Off downloads everything again and deletes it afterwards.")
        string(name: 'BASE_BRANCH', defaultValue: 'main', trim: true,
            description: 'Branch of the viewer repository the pull request targets.')
        booleanParam(name: 'DRY_RUN', defaultValue: false,
            description: 'Only generate and archive the sample JSON; do not open a pull request.')
    }

    environment {
        VIEWER_REPO = 'fajarnuha/gradle-dependency-viewer'
        GITHUB_CREDENTIALS_ID = 'github-credentials'
        SAMPLE_DIR = 'app/static/sample'
        GIT_BOT_NAME = 'gradle-dependency-viewer bot'
        GIT_BOT_EMAIL = 'gradle-dependency-viewer-bot@users.noreply.github.com'
        GRADLE_ARGS = '--no-daemon --console=plain'
    }

    stages {
        // Fails in seconds, instead of after the Gradle run, when the credential cannot push.
        stage('Check GitHub access') {
            when {
                expression { !params.DRY_RUN }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: env.GITHUB_CREDENTIALS_ID,
                        usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                    sh 'python3 jenkins/generate_sample.py check-access --repo "$VIEWER_REPO"'
                }
            }
        }

        stage('Download') {
            steps {
                script {
                    // Outside the checkout, so nothing downloaded can end up in the pull request.
                    env.WORK_DIR = "${env.WORKSPACE}@tmp/generate-sample"
                    env.GRADLE_CACHE_DIR = "${env.HOME}/.cache/gradle-dependency-viewer/gradle"
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
                            # The wrapper gives up on a slow Gradle download after 10s; allow 2 minutes and retry.
                            WRAPPER=gradle/wrapper/gradle-wrapper.properties
                            if grep -q '^networkTimeout=' "$WRAPPER"; then
                                sed -i.bak 's/^networkTimeout=.*/networkTimeout=120000/' "$WRAPPER"
                            else
                                echo 'networkTimeout=120000' >> "$WRAPPER"
                            fi
                            for attempt in 1 2 3; do
                                if ./gradlew $GRADLE_ARGS --version > /dev/null; then break; fi
                                if [ "$attempt" -eq 3 ]; then exit 1; fi
                                echo "Downloading Gradle failed (attempt $attempt), retrying"
                                sleep 15
                            done
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
            // Remove the downloaded project and the generated sample, so the next build starts from a
            // clean checkout. The Gradle cache (GRADLE_CACHE_DIR) is kept.
            // A failed checkout releases the agent before this runs, leaving no workspace to clean.
            script {
                if (env.WORKSPACE) {
                    if (env.WORK_DIR) {
                        dir(env.WORK_DIR) {
                            deleteDir()
                        }
                    }
                    deleteDir()
                }
            }
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

// Runs Gradle steps on the agent. HOME and the Android user home live in WORK_DIR and are deleted
// with it; the Gradle user home is the persistent cache unless CACHE_GRADLE is off. (A job that has
// not run since CACHE_GRADLE was added has no value for it yet, hence the comparison with false.)
def inAndroidEnv(Closure body) {
    def gradleHome = params.CACHE_GRADLE != false ? env.GRADLE_CACHE_DIR : "${env.WORK_DIR}/gradle-home"
    withEnv([
        "HOME=${env.WORK_DIR}/home",
        "GRADLE_USER_HOME=${gradleHome}",
        "ANDROID_USER_HOME=${env.WORK_DIR}/android-home",
    ]) {
        // Every build is untrusted, so remove what one could leave behind for the next to run: Gradle
        // init scripts and properties in the shared Gradle user home.
        sh 'mkdir -p "$HOME" "$GRADLE_USER_HOME" && rm -rf "$GRADLE_USER_HOME/init.d" "$GRADLE_USER_HOME/gradle.properties"'
        body()
    }
}
