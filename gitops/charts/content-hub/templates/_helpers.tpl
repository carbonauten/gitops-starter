{{- define "content-hub.name" -}}
{{- default .Chart.Name .Values.nameOverride -}}
{{- end -}}

{{- define "content-hub.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 -}}
{{- end -}}
