{{/*
Expand the name of the chart.
*/}}
{{- define "gcpFilestoreBackups.name" -}}
{{- default .Chart.Name .Values.nameOverride | lower | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "gcpFilestoreBackups.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "gcpFilestoreBackups.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "gcpFilestoreBackups.labels" -}}
helm.sh/chart: {{ include "gcpFilestoreBackups.chart" . }}
{{ include "gcpFilestoreBackups.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "gcpFilestoreBackups.selectorLabels" -}}
app.kubernetes.io/name: {{ include "gcpFilestoreBackups.name" . | lower }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "gcpFilestoreBackups.serviceAccountName" -}}
{{- if .Values.serviceAccount.name }}
{{- default "default" .Values.serviceAccount.name }}
{{- else }}
{{- default (include "gcpFilestoreBackups.fullname" . | lower ) .Values.serviceAccount.name }}
{{- end }}
{{- end }}
