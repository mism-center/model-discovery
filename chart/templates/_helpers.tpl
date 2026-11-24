{{/*
Expand the name of the chart.
*/}}
{{- define "model-discovery.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "model-discovery.fullname" -}}
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
{{- define "model-discovery.labels" -}}
helm.sh/chart: {{ include "model-discovery.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels for a given component
Usage: {{ include "model-discovery.selectorLabels" (dict "component" "gateway" "context" $) }}
*/}}
{{- define "model-discovery.selectorLabels" -}}
app.kubernetes.io/name: {{ include "model-discovery.name" .context }}
app.kubernetes.io/component: {{ .component }}
app.kubernetes.io/instance: {{ .context.Release.Name }}
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "model-discovery.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Bitnami Redis subchart fullname (mirrors common.names.fullname from the redis chart)
so the parent chart can build service DNS names.
*/}}
{{- define "model-discovery.redis.fullname" -}}
{{- if and .Values.redis .Values.redis.fullnameOverride -}}
{{- .Values.redis.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := "redis" -}}
{{- $releaseName := regexReplaceAll "(-?[^a-z\\d\\-])+-?" (lower .Release.Name) "-" -}}
{{- if contains $name $releaseName -}}
{{- $releaseName | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" $releaseName $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "model-discovery.redis.masterHostname" -}}
{{- printf "%s-master" (include "model-discovery.redis.fullname" .) -}}
{{- end -}}
