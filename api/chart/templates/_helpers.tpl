{{/*
Expand the name of the chart.
*/}}
{{- define "mism-gateway-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "mism-gateway-api.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "mism-gateway-api.labels" -}}
helm.sh/chart: {{ include "mism-gateway-api.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for a given component
Usage: {{ include "mism-gateway-api.selectorLabels" (dict "component" "gateway" "context" $) }}
*/}}
{{- define "mism-gateway-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mism-gateway-api.name" .context }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "mism-gateway-api.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}
