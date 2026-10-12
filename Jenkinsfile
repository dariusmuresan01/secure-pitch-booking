pipeline {
    agent any

    options {
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        COMPOSE_PROJECT_NAME = "spb-ci-${env.BUILD_NUMBER}"
        COMPOSE_FILES = '-f docker-compose.yml -f docker-compose.ci.yml'
    }

    stages {
        stage('Prepare') {
            steps {
                sh '''
                    rm -rf reports keys
                    mkdir -p reports keys
                    chmod 777 reports
                    docker build -f ci/Dockerfile -t spb-ci-tools .
                    sh ci/run-tool.sh python scripts/generate_keys.py
                    chmod 644 keys/*.pem
                '''
            }
        }

        stage('1. Validate dependencies') {
            steps {
                sh '''
                    status=0
                    sh ci/run-tool.sh python scripts/verify_dependencies.py > reports/dependencies.txt 2>&1 || status=$?
                    cat reports/dependencies.txt
                    exit $status
                '''
            }
        }

        stage('2. Build images') {
            steps {
                sh 'docker compose $COMPOSE_FILES --profile test build'
            }
        }

        stage('3. Static analysis') {
            steps {
                sh '''
                    sh ci/run-tool.sh bandit -r api booking-service schedule-service scripts supplier/pitchgrid/src \
                        -f json -o reports/bandit.json --exit-zero
                    sh ci/run-tool.sh bandit -r api booking-service schedule-service scripts supplier/pitchgrid/src \
                        --severity-level high -q
                '''
                sh '''
                    docker run --rm -v "$WORKSPACE":/repo \
                        -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
                        zricethezav/gitleaks:v8.18.4 \
                        detect --source /repo --redact \
                        --report-format json --report-path /repo/reports/gitleaks.json
                '''
            }
        }

        stage('4. Dependency analysis') {
            steps {
                sh '''
                    ignores=$(grep -v '^#' security/audit-exceptions.txt | awk 'NF {print "--ignore-vuln " $1}')
                    for service in api booking-service schedule-service tests; do
                        sh ci/run-tool.sh pip-audit --disable-pip --require-hashes \
                            -r $service/requirements.txt $ignores \
                            -f json -o reports/pip-audit-$service.json
                    done
                '''
            }
        }

        stage('5. Test environment') {
            steps {
                sh 'docker compose $COMPOSE_FILES up -d --wait'
            }
        }

        stage('6. Tests') {
            steps {
                sh '''
                    docker compose $COMPOSE_FILES --profile test run --rm tests \
                        pytest -v -p no:cacheprovider --junitxml=/reports/junit.xml
                '''
            }
        }

        stage('7. Audit log checks') {
            steps {
                sh '''
                    docker compose $COMPOSE_FILES logs --no-color > reports/service-logs.txt
                    if grep -q 'eyJ' reports/service-logs.txt; then
                        echo "FAIL: a token appears in the service logs"
                        exit 1
                    fi
                    if ! grep -q '"status": 403' reports/service-logs.txt; then
                        echo "FAIL: denied requests are not being logged"
                        exit 1
                    fi
                    echo "ok: no tokens in logs, denied requests are logged"
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
            sh '''
                docker compose $COMPOSE_FILES --profile test down -v --remove-orphans || true
                rm -rf keys
            '''
        }
    }
}