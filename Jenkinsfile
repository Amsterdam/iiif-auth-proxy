#!groovy

// Project Settings for Deployment
String PROJECT_DISPLAY = "iiif-auth-proxy"
String PROJECT_NAME = "iiif-auth-proxy"
String CONTAINER_DIR = "."
String PRODUCTION_BRANCH = "master"
String ACCEPTANCE_BRANCH = "development"
String INFRASTRUCTURE = 'thanos'
String PLAYBOOK = 'deploy.yml'

String IMAGE_NAME = "docker-registry.data.amsterdam.nl/datapunt/${PROJECT_NAME}:${env.BUILD_NUMBER}"
String BRANCH = "${env.BRANCH_NAME}"

image = 'initial value'

def tryStep(String message, Closure block, Closure tearDown = null) {
    try {
        block();
    }
    catch (Throwable t) {
        if (BRANCH == "${PRODUCTION_BRANCH}") {
            slackSend message: "${env.JOB_NAME}: ${message} failure ${env.BUILD_URL}", channel: '#ci-channel', color: 'danger'
        }
        throw t;
    }
    finally {
        if (tearDown) {
            tearDown();
        }
    }
}

node {
    // Get a copy of the code
    stage("Checkout") {
        checkout scm
    }

    stage('Test') {
        tryStep "Test", {
            sh "src/deploy/test/jenkins-script.sh"
        }
    }

    // Build the Dockerfile in the $CONTAINER_DIR and push it to Nexus
    stage("Build develop image") {
        tryStep "build", {
            image = docker.build("${IMAGE_NAME}","${CONTAINER_DIR}")
            image.push()
        }
    }
}

// Acceptance branch, fetch the container, label with acceptance and deploy to acceptance.
if (BRANCH == "${ACCEPTANCE_BRANCH}") {
    node {
        stage("Deploy to ACC") {
            tryStep "deployment", {
                image.push("acceptance")
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                        [$class: 'StringParameterValue', name: 'INFRASTRUCTURE', value: "${INFRASTRUCTURE}"],
                        [$class: 'StringParameterValue', name: 'INVENTORY', value: 'acceptance'],
                        [$class: 'StringParameterValue', name: 'PLAYBOOK', value: "${PLAYBOOK}"],
                        [$class: 'StringParameterValue', name: 'PLAYBOOKPARAMS', value: "-e cmdb_id=app_iiif-auth-proxy"]
                ]
            }
        }
  }
}

// On master branch, fetch the container, tag with production and latest and deploy to production
if (BRANCH == "${PRODUCTION_BRANCH}") {
    stage('Waiting for approval') {
        slackSend channel: '#ci-channel', color: 'warning', message: "${PROJECT_DISPLAY} is waiting for Production Release - please confirm"
        input "Deploy to Production?"
    }

    node {
        stage("Deploy to PROD") {
            tryStep "deployment", {
                image.push("production")
                image.push("latest")
                build job: 'Subtask_Openstack_Playbook',
                parameters: [
                        [$class: 'StringParameterValue', name: 'INFRASTRUCTURE', value: "${INFRASTRUCTURE}"],
                        [$class: 'StringParameterValue', name: 'INVENTORY', value: 'production'],
                        [$class: 'StringParameterValue', name: 'PLAYBOOK', value: "${PLAYBOOK}"],
                        [$class: 'StringParameterValue', name: 'PLAYBOOKPARAMS', value: "-e cmdb_id=app_iiif-auth-proxy"]
                ]
            }
        }
    }
}
