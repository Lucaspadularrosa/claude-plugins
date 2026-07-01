# Base de seguridad OWASP (referencia canónica del build)

Este documento es la **fuente única** de la base de seguridad que el pipeline de build
aplica al codificar. Las etapas del build lo consumen para hablar el mismo idioma:

- **`stack-profiler`** deriva de acá qué categorías aplican y las cruza con los
  mecanismos que el stack ofrece, y escribe `.dev/build/security-baseline.json`.
- **`feature-implementer`** aplica estos controles al construir cada tarea.
- **`security-gate`** revisa el diff contra esta base y contra el baseline del stack.

Los agentes llevan una versión concisa de estas categorías inline; **este archivo es la
versión completa y el que se mantiene sincronizado**. Si cambia la base, se cambia acá
primero.

Las etapas de `requirements-pipeline` y `planning-pipeline` usan esta referencia solo de
forma liviana: para tratar la seguridad **específica del dominio** como requisito no
funcional, ADR y tarea/criterio trazables. El **piso genérico** (las 10 categorías de
abajo) no se enumera como requisito: lo garantiza el build por construcción.

---

## Principios (valen para toda categoría)

1. **Mecanismo nativo, no artesanal.** Usá lo que el lenguaje/framework ya da: el ORM
   que parametriza, el template que escapa, el middleware de authz, la librería de
   validación, el gestor de secretos, las primitivas de hashing/cifrado. **Nunca**
   escribas tu propio crypto, tu propio escaping ni tu propio parser de auth. El código
   inseguro casi siempre es código que reinventó algo que el framework ya resolvía.
2. **Por evidencia, no por supuesto.** Qué mecanismo existe en *este* proyecto sale del
   `security-baseline.json` (derivado del repo), no de asumir. Si el baseline dice que
   el stack no da algo nativo, eso es un hueco explícito, no una excusa para improvisar.
3. **Adaptado a la superficie.** OWASP Top 10 está pensado para **apps web**. La suite
   también construye CLIs, librerías y servicios. Aplicá el **subconjunto que aplica** a
   la superficie de la feature (ver tabla abajo); no metas ceremonia web donde no corre.
4. **Prevención, no auditoría.** El build instala el **piso siempre-on**. La auditoría
   profunda adversarial es de `audit-pipeline` (`/auditar`). No se duplican: si un
   hallazgo excede el piso (requiere análisis de flujo, cadena de explotación, revisión
   manual profunda), el `security-gate` lo delega a `/auditar` en vez de simularlo.
5. **Secretos.** Nunca hardcodees claves/tokens/credenciales; salen de config o de un
   secret store. En cualquier reporte se señala el archivo, **nunca** se copia el valor
   del secreto.
6. **Defensa server-side.** Toda validación y todo control de acceso que importe se
   hace del lado del servidor. Los chequeos en el cliente son UX, no seguridad.

---

## Superficie de ataque → categorías aplicables

`stack-profiler` determina la superficie por evidencia (hay rutas HTTP y vistas → web;
hay endpoints sin UI → api; hay un binario/entrypoint de consola → cli; se publica como
paquete → library; corre como proceso/worker → service). La superficie decide qué
categorías tienen sentido:

| OWASP | Riesgo | web | api | cli | library | service |
|---|---|:--:|:--:|:--:|:--:|:--:|
| A01 | Broken Access Control | ✅ | ✅ | ➖ | ➖ | ⚠️ |
| A02 | Cryptographic Failures | ✅ | ✅ | ⚠️ | ⚠️ | ✅ |
| A03 | Injection | ✅ | ✅ | ✅ | ✅ | ✅ |
| A04 | Insecure Design | ✅ | ✅ | ⚠️ | ⚠️ | ✅ |
| A05 | Security Misconfiguration | ✅ | ✅ | ⚠️ | ➖ | ✅ |
| A06 | Vulnerable/Outdated Components | ✅ | ✅ | ✅ | ✅ | ✅ |
| A07 | Identification & Auth Failures | ✅ | ✅ | ➖ | ➖ | ⚠️ |
| A08 | Software & Data Integrity Failures | ✅ | ✅ | ⚠️ | ⚠️ | ✅ |
| A09 | Logging & Monitoring Failures | ✅ | ✅ | ⚠️ | ➖ | ✅ |
| A10 | Server-Side Request Forgery (SSRF) | ✅ | ✅ | ⚠️ | ⚠️ | ✅ |

✅ aplica casi siempre · ⚠️ aplica si la feature lo toca (maneja secretos, entrada
externa, red saliente, deserialización) · ➖ rara vez aplica.

**Transversales a toda superficie:** A03 (inyección), A06 (dependencias vulnerables),
A02 en cuanto haya secretos, y A08 en cuanto haya deserialización o carga dinámica.

---

## OWASP Top 10 (2021) — categorías y defensa

Por cada categoría: qué es, la defensa genérica, el mecanismo nativo típico (ejemplos
cruzando stacks, para ilustrar — el real sale del baseline) y cómo se verifica.

### A01 · Broken Access Control
Un actor accede a un recurso o acción que su rol no debería (rutas sin proteger, IDOR
por cambiar un id, chequeo de rol solo en el cliente, escalada horizontal/vertical).
- **Defensa:** autorizar **cada** acceso del lado del servidor, contra el dueño/rol del
  recurso, con deny-by-default. El `auth_required` de los contratos de API del brief es
  el mínimo, no el techo: además hay que validar *quién* accede a *qué instancia*.
- **Mecanismo nativo:** policies/guards/middleware de autorización (p. ej. Laravel
  Policies/Gates, Django permissions, Spring Security, Rails Pundit/CanCan, filtros de
  autz del framework). Scoping de queries por dueño (`where user_id = current_user`).
- **Verificación:** test que un rol sin permiso recibe 403/redirect y que un usuario no
  puede leer/editar el recurso de otro cambiando el id.

### A02 · Cryptographic Failures
Datos sensibles sin proteger: passwords sin hashear (o con hash débil), PII/tokens en
claro, TLS ausente, algoritmos obsoletos (MD5/SHA1 para passwords, DES), IV/salt fijos.
- **Defensa:** hashear passwords con una función lenta y salada; cifrar datos sensibles
  en tránsito (TLS) y en reposo cuando aplica; no inventar esquemas de cifrado.
- **Mecanismo nativo:** el hasher del framework (bcrypt/argon2/scrypt vía
  `password_hash`, `Django PBKDF2`, `BCrypt` de Spring), la librería de cifrado estándar
  (libsodium, `cryptography`, KMS del cloud). Nunca crypto propio.
- **Verificación:** test que el password se persiste hasheado (no en claro) y que la
  verificación usa la función del framework.

### A03 · Injection
Entrada no confiable interpretada como código/consulta: SQL/NoSQL por concatenación,
comandos de sistema, LDAP, XPath, path traversal, y **XSS** (inyección en la salida
HTML).
- **Defensa:** separar código de datos siempre. Consultas parametrizadas / prepared
  statements o el ORM (nunca `"... WHERE x = " + input`). Para comandos de sistema,
  APIs con argumentos como lista, nunca una shell string. Salida escapada/encodeada al
  contexto (HTML/attr/JS/URL).
- **Mecanismo nativo:** el ORM/query builder (Eloquent, Django ORM, Hibernate, ActiveRecord,
  sqlx con binds), el auto-escaping del motor de templates (Blade, Jinja, Thymeleaf,
  ERB con escape), librerías de sanitización cuando hay HTML de usuario.
- **Verificación:** test con entrada maliciosa (`' OR 1=1`, `<script>`) que no rompe ni
  se refleja sin escapar; grep de queries concatenadas / `eval` / shell strings.

### A04 · Insecure Design
Falla de diseño, no de implementación: falta de límites de negocio, ausencia de rate
limiting, flujos que confían en pasos previos, falta de defensa en profundidad.
- **Defensa:** validar reglas de negocio y límites en el diseño de la feature (montos,
  cantidades, transiciones de estado válidas); rate limiting en acciones sensibles
  (login, reset, endpoints caros); asumir que cualquier paso puede saltearse.
- **Mecanismo nativo:** middleware de throttling/rate-limit del framework, máquinas de
  estado, validación de invariantes en el modelo/servicio.
- **Verificación:** test de los límites y de las transiciones inválidas; esto suele
  aparecer como RNF/criterio específico del brief.

### A05 · Security Misconfiguration
Configuración insegura: debug/verbose en producción, headers de seguridad ausentes,
CORS abierto (`*` con credenciales), directorios listables, defaults inseguros, cuentas
o endpoints de ejemplo activos.
- **Defensa:** secure-by-default; debug apagado fuera de dev; CORS restrictivo; headers
  de seguridad (CSP, HSTS, X-Content-Type-Options) donde el framework los ofrezca;
  errores genéricos al usuario.
- **Mecanismo nativo:** middleware de security headers, config por entorno del framework,
  el modo producción del framework.
- **Verificación:** inspección de config; que el entorno de producción no exponga debug
  ni stack traces.

### A06 · Vulnerable and Outdated Components
Dependencias con vulnerabilidades conocidas (CVE), versiones sin soporte, librerías
traídas sin necesidad.
- **Defensa:** no introducir dependencias nuevas que el diseño no pida; correr el audit
  de dependencias del stack y no dejar entrar críticas/altas conocidas.
- **Mecanismo nativo:** el comando de audit del ecosistema — `npm audit`, `pnpm audit`,
  `composer audit`, `pip-audit`, `govulncheck`, `bundler-audit`, `cargo audit`,
  `dotnet list package --vulnerable`.
- **Verificación:** el `security-gate` corre el `dependency_audit` del baseline; el
  `feature-implementer` lo corre antes de dar una tarea por hecha si tocó dependencias.

### A07 · Identification and Authentication Failures
Autenticación débil: sin protección contra fuerza bruta, sesiones/tokens mal manejados,
credenciales por defecto, recuperación de cuenta insegura, ausencia de MFA donde se pide.
- **Defensa:** usar el sistema de auth del framework; sesiones/tokens con expiración,
  rotación e invalidación; cookies con `HttpOnly`/`Secure`/`SameSite`; throttling de login.
- **Mecanismo nativo:** el guard/módulo de auth del framework (Laravel Auth/Sanctum,
  Django auth, Spring Security, Devise), su manejo de sesión y de cookies.
- **Verificación:** test de expiración/invalidez de sesión y de flags de cookie; login
  con throttling.

### A08 · Software and Data Integrity Failures
Confiar en datos/código sin verificar integridad: **deserialización insegura**, updates
o plugins sin firmar, pipelines que ejecutan artefactos no verificados, mass assignment.
- **Defensa:** no deserializar formatos peligrosos con datos de usuario; whitelistear
  campos asignables (contra mass assignment); verificar integridad de artefactos externos.
- **Mecanismo nativo:** `$fillable`/`$guarded` o DTOs/serializers con campos explícitos,
  parsers seguros (JSON en vez de pickle/serialize nativo con datos externos).
- **Verificación:** test que un campo no permitido no se asigna vía payload; grep de
  deserialización nativa sobre entrada de usuario.

### A09 · Security Logging and Monitoring Failures
No registrar eventos de seguridad, o registrarlos con datos sensibles: sin logs de
login fallido/acceso denegado, o logs que filtran passwords/tokens/PII.
- **Defensa:** loguear eventos de seguridad relevantes (auth, autz denegada, fallos de
  validación) sin datos sensibles en claro; errores al usuario genéricos, detalle al log.
- **Mecanismo nativo:** el logger del framework con niveles y redacción; middleware de
  auditoría.
- **Verificación:** inspección de que los eventos clave se loguean y de que ningún log
  emite secretos/PII.

### A10 · Server-Side Request Forgery (SSRF)
El servidor hace una request a una URL que controla el usuario, y se la puede apuntar a
la red interna o a metadata del cloud (169.254.169.254).
- **Defensa:** no dejar que la entrada de usuario decida el host de una request saliente;
  whitelist de destinos, resolver y validar la IP (bloquear rangos privados/loopback),
  no seguir redirects ciegamente.
- **Mecanismo nativo:** clientes HTTP con allowlist/validación, librerías anti-SSRF del
  ecosistema.
- **Verificación:** test que una URL interna/privada es rechazada; aplica solo si la
  feature hace requests salientes con destino influido por el usuario.

---

## Tooling de verificación (por evidencia del stack)

`stack-profiler` registra en `security-baseline.json > tooling` los comandos reales del
proyecto, marcando `validated` cuando pudo correrlos:

- **`dependency_audit`** (A06): `npm/pnpm/yarn audit`, `composer audit`, `pip-audit`,
  `govulncheck`, `bundler-audit`, `cargo audit`, `dotnet list package --vulnerable`.
- **`sast`** (opcional, si existe en el repo/CI): `semgrep`, `eslint-plugin-security`,
  `bandit` (Python), `brakeman` (Rails), `gosec` (Go), `psalm/phpstan` con reglas de
  seguridad.
- **`secret_scan`** (opcional): `gitleaks`, `trufflehog`, `detect-secrets` si el repo
  los usa.

Si un comando no existe para el stack, va como `warning`/`open_question` del baseline:
la ausencia se declara, no se finge.

---

## Cómo lo usa cada etapa (resumen)

- **`stack-profiler`** → cruza esta referencia con el repo y emite
  `security-baseline.json` (superficie, categorías aplicables, mecanismo nativo por
  categoría, tooling), por evidencia.
- **`feature-implementer`** → por cada tarea, aplica el control de cada categoría
  aplicable usando el mecanismo del baseline; corre el `dependency_audit` si tocó deps;
  reporta qué controles aplicó.
- **`security-gate`** → revisa el diff contra el baseline y las categorías aplicables,
  corre el `dependency_audit`, emite hallazgos con `owasp_id` y delega a `/auditar` lo
  que excede el piso.
- **`requirements-specification` / `technical-design` / `task-derivation` /
  `feature-brief`** → tratan la seguridad **específica del dominio** como RNF, ADR y
  tarea/criterio trazables. El piso genérico de arriba no se enumera: lo cubre el build.
