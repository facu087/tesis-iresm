# Spec Delta

## Purpose

Define qué proveedor y qué modelo de lenguaje usa cada agente, cómo se activa la
arquitectura de destino de la tesis y cómo el sistema sigue funcionando y lo informa
cuando un proveedor no está disponible.

## ADDED Requirements

### Requirement: Asignación de proveedor por agente

Con la arquitectura de destino activa, el sistema SHALL usar Anthropic (Claude Opus)
para los Agentes 01, 04 y 06, OpenAI (GPT-4o) para el Agente 02 y Google (Gemini Pro)
para el Agente 03, en todas las llamadas que cada agente hace, incluidas las del debate.

#### Scenario: Llamada de un agente con proveedor asignado
- **WHEN** la arquitectura de destino está activa, la clave del proveedor está configurada y el Agente 02 escribe su crítica en la Ronda 2
- **THEN** esa llamada se hace a OpenAI con el modelo asignado al Agente 02

#### Scenario: Debate con tres proveedores
- **WHEN** la arquitectura de destino está activa con las tres claves configuradas y corre el debate
- **THEN** las llamadas de los Agentes 01, 02 y 03 van a Anthropic, OpenAI y Google respectivamente

### Requirement: Llamadas que siguen en Groq

Las llamadas que no son de un agente con proveedor asignado SHALL seguir en Groq con
el modelo de hoy, también con la arquitectura de destino activa: la síntesis PICO, la
extracción de biomarcadores y las del Agente 05.

#### Scenario: Síntesis PICO con la arquitectura de destino activa
- **WHEN** la arquitectura de destino está activa y se arma la síntesis PICO
- **THEN** la llamada va a Groq, igual que hoy

#### Scenario: Agente 05 con la arquitectura de destino activa
- **WHEN** la arquitectura de destino está activa y el Agente 05 planifica los términos de búsqueda
- **THEN** la llamada va a Groq, igual que hoy

### Requirement: Activación explícita y comportamiento por defecto sin cambios

La arquitectura de destino SHALL activarse por configuración explícita y estar
desactivada por defecto. Desactivada, toda llamada MUST ir a Groq con el mismo modelo
y techo que hoy, aunque haya claves de otros proveedores configuradas.

#### Scenario: Sin activar, con claves presentes
- **WHEN** la arquitectura de destino no está activa y la clave de Anthropic está configurada
- **THEN** el Agente 01 llama a Groq y no se hace ninguna llamada a Anthropic

#### Scenario: Valor de activación no reconocido
- **WHEN** la variable de activación tiene un valor que no es el de la arquitectura de destino ni el de Groq
- **THEN** el sistema avisa por stderr y se comporta como desactivada

### Requirement: Respaldo en Groq por clave faltante

Con la arquitectura de destino activa, si falta la clave del proveedor asignado a un
agente, las llamadas de ese agente SHALL hacerse en Groq con el modelo de hoy, y el
sistema MUST avisarlo por stderr una vez por análisis y por proveedor.

#### Scenario: Falta la clave de Google
- **WHEN** la arquitectura de destino está activa sin la clave de Google y el Agente 03 genera sus hipótesis
- **THEN** la llamada va a Groq, el análisis continúa y stderr avisa que el Agente 03 usó el respaldo por falta de clave

#### Scenario: Ninguna clave de destino
- **WHEN** la arquitectura de destino está activa sin ninguna de las tres claves
- **THEN** el análisis completa igual que hoy, con todas las llamadas en Groq y marcadas como respaldo

### Requirement: Respaldo en Groq por falla del proveedor

Si la llamada a un proveedor de destino falla después de sus reintentos, esa llamada
SHALL repetirse en Groq con el modelo de hoy y el análisis MUST continuar. Una falla de
Groq en el respaldo se propaga como hoy.

#### Scenario: Anthropic no responde
- **WHEN** la llamada del Agente 04 a Anthropic falla por error del servicio en todos sus intentos
- **THEN** la misma llamada se hace en Groq y el arbitraje continúa con esa respuesta

#### Scenario: Clave inválida
- **WHEN** la clave de OpenAI está configurada pero el proveedor la rechaza
- **THEN** la llamada del Agente 02 se hace en Groq y queda registrada como respaldo por falla

### Requirement: El reporte informa quién respondió

El reporte SHALL incluir, por cada agente que llamó al modelo, el proveedor y el modelo
que respondieron y si alguna de sus llamadas usó el respaldo y por qué (clave faltante
o falla). La información MUST verse en la vista del reporte y en el PDF.

#### Scenario: Corrida completa en la arquitectura de destino
- **WHEN** termina un análisis con la arquitectura de destino activa y las tres claves válidas
- **THEN** el reporte muestra Claude Opus para los Agentes 01, 04 y 06, GPT-4o para el 02 y Gemini Pro para el 03, sin respaldos

#### Scenario: Corrida con respaldo
- **WHEN** termina un análisis en el que el Agente 03 usó el respaldo por clave faltante
- **THEN** el reporte muestra que el Agente 03 respondió con Groq y el motivo del respaldo

#### Scenario: Reporte anterior a este cambio
- **WHEN** se muestra un reporte guardado antes de este cambio, sin la información de proveedores
- **THEN** la vista y el PDF se generan sin error y omiten esa sección

### Requirement: Los datos clínicos no salen por un canal nuevo de diagnóstico

Los avisos de respaldo y la información de proveedores del reporte MUST limitarse a
identificadores de agente, proveedor, modelo y motivo. MUST NOT incluir el prompt, la
respuesta ni el texto del mensaje de error del proveedor, que puede arrastrar contenido.

#### Scenario: Aviso de falla del proveedor
- **WHEN** una llamada a Anthropic falla con un error cuyo mensaje incluye parte del prompt
- **THEN** stderr y el reporte registran solo el agente, el proveedor y el tipo de falla, sin el mensaje

### Requirement: El modo mock no cambia

En modo mock, ninguna llamada SHALL llegar a un proveedor, con o sin la arquitectura de
destino activa: las respuestas grabadas se entregan igual que hoy.

#### Scenario: Modo mock con la arquitectura de destino activa
- **WHEN** el modo mock y la arquitectura de destino están activos a la vez
- **THEN** el análisis usa las respuestas grabadas y no se hace ninguna llamada de red a ningún proveedor
