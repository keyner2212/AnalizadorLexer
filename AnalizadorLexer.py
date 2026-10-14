#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR LÉXICO + SINTÁCTICO GENÉRICO (C / C++ / Java / JavaScript / Python...)
CON INTERFAZ GRÁFICA — TODO EN UN SOLO ARCHIVO.

Uso (guárdalo como analizador.py):
    python analizador.py              -> abre la ventana: pega tu código y pulsa ANALIZAR
    python analizador.py archivo.c    -> abre la ventana con ese archivo ya cargado

Como librería (sin ventana):
    from analizador import AnalizadorCodigo
    print(AnalizadorCodigo("if (a<10) {a++;}").analizar().reporte())

Garantías de diseño:
  * El análisis léxico NUNCA falla: lo que no reconoce lo marca como DESCONOCIDO y sigue.
  * El análisis sintáctico NUNCA aborta: reporta errores con línea/columna y se recupera.
  * Es "genérico": no usa la gramática exacta de un lenguaje, sino una gramática tolerante
    (expresiones con precedencia, bloques {} o indentados con ':', declaraciones, funciones,
    clases, control de flujo, listas/diccionarios, lambdas, etc.).
"""
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import List, Optional

# --------------------------------------------------------------------------
# Tipos de token
# --------------------------------------------------------------------------
PR, ID, NUM, CAD, OP = "PALABRA_RESERVADA", "IDENTIFICADOR", "NUMERO", "CADENA", "OPERADOR"
DEL, PYC, COM, DIR, DESC, FIN = ("DELIMITADOR", "PUNTO_Y_COMA", "COMENTARIO",
                                 "DIRECTIVA", "DESCONOCIDO", "FIN")

# --------------------------------------------------------------------------
# Perfil de palabras (unión de varios lenguajes). Edítalo para ajustar a tu lenguaje.
# --------------------------------------------------------------------------
CONTROL_CON_CABECERA = {"if", "elif", "elsif", "while", "for", "foreach", "switch",
                        "catch", "except", "with", "until", "unless"}
CONTROL_SIN_CABECERA = {"else", "try", "finally", "loop"}
CONTINUACION = {"else", "elif", "elsif", "catch", "except", "finally"}
DEFINICIONES = {"def", "function", "fn", "func", "fun", "class", "struct", "enum",
                "interface", "namespace", "union", "trait", "impl", "module", "record"}
SIMPLES = {"return", "break", "continue", "throw", "raise", "import", "from", "using",
           "package", "pass", "del", "global", "nonlocal", "assert", "yield", "goto",
           "require", "include", "exit"}
SALTABLES = {"as", "import", "from", "static", "of", "type"}
TIPOS = {"int", "float", "double", "char", "void", "long", "short", "string", "bool",
         "boolean", "byte", "var", "let", "auto", "unsigned", "signed", "number",
         "decimal", "object", "wchar_t", "size_t"}
MODIFICADORES = {"const", "static", "final", "public", "private", "protected", "abstract",
                 "volatile", "extern", "register", "inline", "readonly", "async",
                 "override", "virtual", "synchronized", "transient", "mut", "pub",
                 "export", "typedef", "sealed", "internal", "partial"}
LITERALES = {"true", "false", "null", "none", "nil", "this", "self", "super",
             "undefined", "nan"}
OPS_PALABRA = {"and", "or", "not", "in", "is", "instanceof"}
UNARIOS_PALABRA = {"not", "new", "delete", "typeof", "sizeof", "await"}
OTRAS_PALABRAS = {"case", "default", "do", "lambda", "as", "extends", "implements",
                  "of", "throws", "where", "enum", "in", "is", "and", "or", "not",
                  "new", "delete", "typeof", "sizeof", "await", "instanceof", "end",
                  "then", "begin", "print"}
OTRAS_PALABRAS.discard("print")
PALABRAS_RESERVADAS = (CONTROL_CON_CABECERA | CONTROL_SIN_CABECERA | DEFINICIONES |
                       SIMPLES | TIPOS | MODIFICADORES | LITERALES | OPS_PALABRA |
                       OTRAS_PALABRAS)
CONTROL_TODO = CONTROL_CON_CABECERA | CONTROL_SIN_CABECERA | {"do"}
PALABRAS_DE_SENTENCIA = (CONTROL_TODO | (DEFINICIONES - {"function", "fn", "func", "fun"}) |
                         SIMPLES | {"case", "default"})
ENCABEZADOS_PY = {"if", "elif", "else", "for", "while", "def", "class", "try",
                  "except", "finally", "with"}

ASIGNACION = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
              ">>>=", "**=", ":=", "=>"}
PRECEDENCIA = {"??": 1, "||": 2, "or": 2, "&&": 3, "and": 3, "|": 4, "^": 5, "&": 6,
               "==": 7, "!=": 7, "===": 7, "!==": 7, "<": 8, ">": 8, "<=": 8, ">=": 8,
               "in": 8, "is": 8, "instanceof": 8, "not in": 8, "is not": 8,
               "<<": 9, ">>": 9, ">>>": 9, "+": 10, "-": 10, "*": 11, "/": 11,
               "%": 11, "**": 12}
UNARIOS_OP = {"!", "~", "-", "+", "++", "--", "*", "&", "@", "..."}

NOMBRES_OP = {
    "+": "operador suma", "-": "operador resta", "*": "operador multiplicación",
    "/": "operador división", "%": "operador módulo", "=": "operador de asignación",
    "==": "operador de igualdad", "!=": "operador de desigualdad",
    "===": "igualdad estricta", "!==": "desigualdad estricta",
    "<": "operador de menor", ">": "operador de mayor",
    "<=": "operador de menor o igual", ">=": "operador de mayor o igual",
    "++": "incremento", "--": "decremento", "&&": "operador lógico AND",
    "||": "operador lógico OR", "!": "operador lógico NOT",
    "&": "operador AND a nivel de bits", "|": "operador OR a nivel de bits",
    "^": "operador XOR", "~": "operador NOT a nivel de bits",
    "<<": "desplazamiento a la izquierda", ">>": "desplazamiento a la derecha",
    ">>>": "desplazamiento sin signo", "**": "operador potencia",
    "->": "acceso por puntero / flecha", "=>": "flecha (lambda)",
    "::": "resolución de ámbito", ".": "acceso a miembro", "?": "operador ternario",
    "??": "coalescencia nula", "?.": "acceso opcional", "...": "operador de expansión",
    "@": "arroba / decorador", ":=": "asignación (walrus)",
}


# --------------------------------------------------------------------------
# Token
# --------------------------------------------------------------------------
@dataclass
class Token:
    tipo: str
    lexema: str
    linea: int
    col: int
    nl_antes: bool = False   # True si hay un salto de línea entre este token y el anterior

    @property
    def descripcion(self) -> str:
        if self.tipo == PR:
            return "palabra reservada"
        if self.tipo == ID:
            return "identificador"
        if self.tipo == NUM:
            return "número"
        if self.tipo == CAD:
            return "cadena de texto"
        if self.tipo == PYC:
            return "punto y coma"
        if self.tipo == COM:
            return "comentario"
        if self.tipo == DIR:
            return "directiva de preprocesador"
        if self.tipo == DESC:
            return "carácter desconocido"
        if self.tipo == OP:
            if self.lexema in NOMBRES_OP:
                return NOMBRES_OP[self.lexema]
            if self.lexema.endswith("=") and len(self.lexema) > 1:
                return "operador de asignación compuesta"
            return "operador"
        if self.tipo == DEL:
            return {",": "coma", ":": "dos puntos"}.get(self.lexema, "delimitador")
        return self.tipo.lower()


# --------------------------------------------------------------------------
# ANÁLISIS LÉXICO
# --------------------------------------------------------------------------
class AnalizadorLexico:
    """Convierte texto en tokens. Nunca lanza excepciones por entrada inválida."""

    _OPS = [">>>=", "<<=", ">>=", ">>>", "...", "===", "!==", "**=", "->", "=>", "::",
            "++", "--", "&&", "||", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
            "&=", "|=", "^=", "<<", ">>", "**", "??", "?.", ":=",
            "+", "-", "*", "/", "%", "=", "<", ">", "!", "&", "|", "^", "~", "?", ".", "@"]

    _PATRON = re.compile("|".join(f"(?P<{n}>{p})" for n, p in [
        ("COMBLOQ", r"/\*.*?(?:\*/|\Z)"),
        ("COMLIN", r"//[^\n]*"),
        ("DIRECT", r"\#[ \t]*(?:include|define|undef|ifdef|ifndef|if|else|elif|endif|"
                   r"pragma|error)\b[^\n]*"),
        ("COMHASH", r"\#[^\n]*"),
        ("CADTRI1", r'""".*?(?:"""|\Z)'),
        ("CADTRI2", r"'''.*?(?:'''|\Z)"),
        ("CAD1", r'"(?:\\.|[^"\\\n])*"?'),
        ("CAD2", r"'(?:\\.|[^'\\\n])*'?"),
        ("CAD3", r"`(?:\\.|[^`\\])*`?"),
        ("CADTIP", r"[“”„«][^“”„«»\n]*[“”»]?"),
        ("CADTIP2", r"[‘’][^‘’\n]*[‘’]?"),
        ("NUM", r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|"
                r"(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?[fFlLuUjJ]*"),
        ("ID", r"[^\W\d][\w$]*|\$[\w$]*"),
        ("WS", r"\s+"),
        ("OP", "|".join(re.escape(o) for o in sorted(_OPS, key=len, reverse=True))),
        ("PYC", r";"),
        ("DEL", r"[()\[\]{},:]"),
        ("DESC", r"."),
    ]), re.DOTALL)

    def __init__(self, sensible_mayusculas: bool = False):
        self.sensible = sensible_mayusculas
        self.errores: List[str] = []

    def tokenizar(self, codigo: str) -> List[Token]:
        tokens: List[Token] = []
        self.errores = []
        try:
            codigo = (codigo or "").replace("\r\n", "\n").replace("\r", "\n")
            linea, inicio_linea, ult_fin = 1, 0, 0
            for m in self._PATRON.finditer(codigo):
                g, lex, pos = m.lastgroup, m.group(), m.start()
                col = pos - inicio_linea + 1
                n_saltos = lex.count("\n")
                if g != "WS":
                    tipo = self._tipo(g, lex)
                    if tipo is not None:
                        nl = linea > ult_fin if tipo not in (COM, DIR) else False
                        tokens.append(Token(tipo, lex, linea, col, nl))
                        self._avisos(tipo, g, lex, linea, col)
                        if tipo not in (COM,):
                            ult_fin = linea + n_saltos
                if n_saltos:
                    linea += n_saltos
                    inicio_linea = pos + lex.rfind("\n") + 1
        except Exception as e:  # red de seguridad: jamás abortar
            self.errores.append(f"Aviso interno del analizador léxico: {e}")
        return tokens

    def _tipo(self, g, lex):
        if g in ("COMBLOQ", "COMLIN", "COMHASH"):
            return COM
        if g == "DIRECT":
            return DIR
        if g.startswith("CAD"):
            return CAD
        if g == "NUM":
            return NUM
        if g == "ID":
            clave = lex if self.sensible else lex.lower()
            return PR if clave in PALABRAS_RESERVADAS else ID
        if g == "OP":
            return OP
        if g == "PYC":
            return PYC
        if g == "DEL":
            return DEL
        return DESC

    def _avisos(self, tipo, g, lex, linea, col):
        if g == "COMBLOQ" and not lex.endswith("*/"):
            self.errores.append(f"Línea {linea}, col {col}: comentario de bloque sin cerrar")
        elif g in ("CAD1", "CAD2") and (len(lex) < 2 or lex[-1] != lex[0]):
            self.errores.append(f"Línea {linea}, col {col}: cadena sin cerrar {lex[:20]!r}")
        elif g == "CAD3" and (len(lex) < 2 or lex[-1] != "`"):
            self.errores.append(f"Línea {linea}, col {col}: cadena sin cerrar")
        elif g in ("CADTRI1", "CADTRI2") and (len(lex) < 6 or lex[-3:] != lex[:3]):
            self.errores.append(f"Línea {linea}, col {col}: cadena de triple comilla sin cerrar")
        elif tipo == DESC:
            self.errores.append(f"Línea {linea}, col {col}: carácter desconocido {lex!r}")

    @staticmethod
    def tabla(tokens: List[Token], mostrar_comentarios: bool = False) -> str:
        filas = [t for t in tokens if mostrar_comentarios or t.tipo not in (COM,)]
        ancho = min(30, max([len(t.lexema.splitlines()[0] if t.lexema else "") for t in filas] + [6]))
        sal = [f"{'LEXEMA':<{ancho}}  {'TIPO':<30}  LÍNEA:COL", "-" * (ancho + 48)]
        for t in filas:
            lex = (t.lexema.splitlines() or [""])[0]
            if len(lex) > ancho:
                lex = lex[:ancho - 3] + "..."
            sal.append(f"{lex:<{ancho}}  {t.descripcion:<30}  {t.linea}:{t.col}")
        return "\n".join(sal)


# --------------------------------------------------------------------------
# Árbol sintáctico
# --------------------------------------------------------------------------
class Nodo:
    def __init__(self, tipo, valor=None, hijos=None, linea=0):
        self.tipo, self.valor, self.hijos, self.linea = tipo, valor, list(hijos or []), linea

    def agregar(self, h):
        if h is not None:
            self.hijos.append(h)
        return h

    def dibujar(self, prefijo="", ultimo=True, raiz=True):
        etiqueta = self.tipo + (f": {self.valor}" if self.valor not in (None, "") else "")
        if raiz:
            sal, nuevo = [etiqueta], ""
        else:
            sal = [prefijo + ("└── " if ultimo else "├── ") + etiqueta]
            nuevo = prefijo + ("    " if ultimo else "│   ")
        for k, h in enumerate(self.hijos):
            sal += h.dibujar(nuevo, k == len(self.hijos) - 1, False)
        return sal

    def contar(self):
        return 1 + sum(h.contar() for h in self.hijos)


# --------------------------------------------------------------------------
# ANÁLISIS SINTÁCTICO (descenso recursivo tolerante, con recuperación de errores)
# --------------------------------------------------------------------------
class AnalizadorSintactico:
    MAX_ERRORES = 300

    def __init__(self, tokens: List[Token], punto_y_coma="auto"):
        self.toks = [t for t in tokens if t.tipo not in (COM, DIR)]
        ult = self.toks[-1] if self.toks else None
        self.fin = Token(FIN, "", ult.linea if ult else 1,
                         (ult.col + len(ult.lexema)) if ult else 1, True)
        self.i = 0
        self.prof = 0       # profundidad de ( [ { en expresiones (permite saltos de línea)
        self.sin_if = 0     # >0 dentro de comprensiones (desactiva "a if c else b")
        self.errores: List[tuple] = []
        self.exigir_pyc = (self._detectar_pyc() if punto_y_coma == "auto"
                           else bool(punto_y_coma))

    # ---------------- utilidades ----------------
    def _t(self, j):
        return self.toks[j] if 0 <= j < len(self.toks) else self.fin

    def tok(self, k=0):
        return self._t(self.i + k)

    def prev(self):
        return self._t(self.i - 1) if self.i > 0 else self.fin

    def avanzar(self):
        t = self.tok()
        if t.tipo != FIN:
            self.i += 1
        return t

    def es(self, lex, k=0):
        t = self.tok(k)
        return t.lexema == lex and t.tipo in (OP, DEL, PYC)

    def kw(self, k=0):
        t = self.tok(k)
        return t.lexema.lower() if t.tipo == PR else ""

    def desc(self, t):
        if t.tipo == FIN:
            return "el final del código"
        l = t.lexema if len(t.lexema) <= 25 else t.lexema[:22] + "..."
        return f"'{l}'"

    def error(self, msg, t=None):
        t = t or self.tok()
        e = (t.linea, t.col, msg)
        if e not in self.errores and len(self.errores) < self.MAX_ERRORES:
            self.errores.append(e)

    def _detectar_pyc(self):
        if not any(t.tipo == PYC for t in self.toks):
            return False
        primero = None
        for idx, t in enumerate(self.toks):
            if t.nl_antes:
                primero = t
            if t.lexema == ":" and t.tipo == DEL and primero is not None \
                    and primero.lexema.lower() in ENCABEZADOS_PY:
                sig = self.toks[idx + 1] if idx + 1 < len(self.toks) else None
                if sig is None or sig.nl_antes:
                    return False
        return True

    def _continua(self, t):
        """¿Puede esta expresión continuar en una nueva línea con el token t?"""
        return not (t.nl_antes and self.prof == 0 and not self.exigir_pyc)

    def _terminador(self):
        t = self.tok()
        return (t.tipo == FIN or self.es(";") or self.es("}") or
                (not self.exigir_pyc and t.nl_antes and self.prof == 0))

    def _fin_operando(self):
        t = self.tok()
        return t.tipo == FIN or (t.tipo in (DEL, PYC) and t.lexema in (")", "]", "}", ";", ","))

    def _esperar(self, lex, contexto, abre=None):
        if self.es(lex):
            return self.avanzar()
        t = self.tok()
        extra = f" (abierto en la línea {abre.linea})" if abre else ""
        self.error(f"Se esperaba '{lex}' {contexto}{extra}, pero se encontró {self.desc(t)}",
                   t if t.tipo != FIN else self.prev())
        return None

    def _sincronizar(self):
        primero = True
        while self.tok().tipo != FIN:
            t = self.tok()
            if t.tipo == PYC:
                self.i += 1
                return
            if self.es("}"):
                return
            if not primero and not self.exigir_pyc and t.nl_antes:
                return
            self.i += 1
            primero = False

    def _cerrar(self, n_err, ultimo):
        """Cierre de una sentencia simple: ';' (o salto de línea en lenguajes sin ';')."""
        if self.es(";"):
            self.avanzar()
            return
        if len(self.errores) > n_err:
            self._sincronizar()
            return
        t = self.tok()
        if t.tipo == FIN or self.es("}") or t.nl_antes:
            if self.exigir_pyc:
                self.error("Se esperaba ';' al final de la sentencia", ultimo)
            return
        if self.exigir_pyc:
            self.error(f"Se esperaba ';' pero se encontró {self.desc(t)}", t)
        else:
            self.error(f"Símbolo inesperado {self.desc(t)}", t)
        self._sincronizar()

    # ---------------- punto de entrada ----------------
    def analizar(self) -> Nodo:
        raiz = Nodo("Programa")
        try:
            while self.tok().tipo != FIN:
                if self.es("}"):
                    self.error("Llave de cierre '}' sin su llave de apertura")
                    self.avanzar()
                    continue
                self._sentencia_segura(raiz)
        except Exception as e:  # red de seguridad (p. ej. recursión excesiva)
            self.error(f"Error interno del analizador sintáctico: {type(e).__name__}",
                       self.tok())
        return raiz

    def _sentencia_segura(self, padre):
        antes = self.i
        padre.agregar(self.parse_sentencia())
        if self.i == antes:
            self.error(f"Símbolo inesperado {self.desc(self.tok())}")
            self.avanzar()

    # ---------------- sentencias ----------------
    def parse_sentencia(self):
        t = self.tok()
        k = self.kw()
        if self.es(";"):
            self.avanzar()
            return Nodo("Sentencia vacía", linea=t.linea)
        if self.es("{"):
            return self.parse_bloque()
        if self.es("}"):
            self.error("Se esperaba una sentencia pero se encontró '}'")
            return Nodo("Error")
        if self.es("@"):                      # anotación / decorador
            self.avanzar()
            n = Nodo("Anotación", linea=t.linea)
            n.agregar(self.parse_postfijo())
            return n
        if k in MODIFICADORES:                # saltar modificadores antes de class/function...
            j = self.i
            while True:
                x = self._t(j)
                if x.tipo == PR and (x.lexema.lower() in MODIFICADORES or
                                     (x.lexema.lower() == "default" and
                                      self._t(j - 1).lexema.lower() == "export")):
                    j += 1
                else:
                    break
            x = self._t(j)
            if x.tipo == PR and x.lexema.lower() in DEFINICIONES | CONTROL_TODO:
                self.i = j
                return self.parse_sentencia()
            if k in MODIFICADORES and self.es(":", 1):       # public: / private:
                self.avanzar()
                self.avanzar()
                return Nodo(f"Etiqueta {t.lexema}", linea=t.linea)
        k = self.kw()
        if k in CONTROL_CON_CABECERA or k in CONTROL_SIN_CABECERA:
            return self.parse_control()
        if k == "do":
            return self.parse_do()
        if k in DEFINICIONES:
            return self.parse_definicion()
        if k in ("case", "default"):
            return self.parse_etiqueta()
        if k in SIMPLES:
            return self.parse_simple()
        if self.es_declaracion():
            return self.parse_declaracion()
        # sentencia de expresión
        n_err = len(self.errores)
        nodo = Nodo("Sentencia de expresión", linea=t.linea)
        nodo.agregar(self.parse_expresion())
        while self.es(","):
            self.avanzar()
            nodo.agregar(self.parse_expresion())
        if self.es(":") and len(self.errores) == n_err:      # anotación x: int  /  etiqueta:
            self.avanzar()
            if not self._terminador():
                nodo.agregar(self.parse_expresion())
        self._cerrar(n_err, self.prev())
        return nodo

    def parse_bloque(self):
        ap = self.avanzar()  # '{'
        nodo = Nodo("Bloque", linea=ap.linea)
        guardado, self.prof = self.prof, 0
        while self.tok().tipo != FIN and not self.es("}"):
            self._sentencia_segura(nodo)
        self._esperar("}", "para cerrar el bloque", ap)
        self.prof = guardado
        return nodo

    def parse_cuerpo(self, kw):
        if self.es("{"):
            return self.parse_bloque()
        if self.es(":"):
            dp = self.avanzar()
            if self.tok().tipo != FIN and self.tok().nl_antes:
                nodo = Nodo("Bloque (indentado)", linea=dp.linea)
                while (self.tok().tipo != FIN and self.tok().col > kw.col
                       and not self.es("}")):
                    self._sentencia_segura(nodo)
                if not nodo.hijos:
                    self.error(f"Se esperaba un bloque indentado después de ':'", dp)
                return nodo
            if self.tok().tipo == FIN or self.es("}"):
                self.error(f"Se esperaba el cuerpo de '{kw.lexema}' después de ':'", dp)
                return Nodo("Error")
            return self.parse_sentencia()
        if self.es(";"):
            self.avanzar()
            return Nodo("Sentencia vacía", linea=kw.linea)
        if self.tok().tipo == FIN or self.es("}"):
            self.error(f"Se esperaba el cuerpo de '{kw.lexema}'", self.prev())
            return Nodo("Error")
        return self.parse_sentencia()

    def parse_control(self, continuacion=False):
        kw = self.avanzar()
        k = kw.lexema.lower()
        nodo = Nodo(f"Sentencia {kw.lexema}", linea=kw.linea)
        if not continuacion and k in CONTINUACION:
            self.error(f"'{kw.lexema}' sin una sentencia 'if'/'try' previa", kw)
        if k in CONTROL_CON_CABECERA:
            nodo.agregar(self.parse_cabecera(kw))
        nodo.agregar(self.parse_cuerpo(kw))
        while self.kw() in CONTINUACION and (self.tok().col >= kw.col or not self.tok().nl_antes):
            nodo.agregar(self.parse_control(continuacion=True))
        return nodo

    def parse_cabecera(self, kw):
        nodo = Nodo("Condición" if kw.lexema.lower() in ("if", "elif", "elsif", "while",
                                                          "until", "unless") else "Cabecera",
                    linea=kw.linea)
        if self.es("("):
            ap = self.avanzar()
            self.prof += 1
            if self.es(")"):
                self.error(f"Falta la condición en '{kw.lexema}'", ap)
            fallo = False
            while self.tok().tipo != FIN and not self.es(")") and not self.es("{"):
                antes = self.i
                if self.es(";") or self.es(",") or self.es(":"):
                    self.avanzar()
                    continue
                if self.es_declaracion():
                    nodo.agregar(self.parse_declaracion(cerrar=False))
                else:
                    nodo.agregar(self.parse_expresion())
                if self.kw() in ("of", "in"):
                    self.avanzar()
                    continue
                if not (self.es(";") or self.es(",") or self.es(":") or self.es(")")
                        or self.es("{") or self.tok().tipo == FIN):
                    self.error(f"Se esperaba ';' o ')' en la cabecera de '{kw.lexema}' "
                               f"pero se encontró {self.desc(self.tok())}")
                    fallo = True
                    break
                if self.i == antes:
                    self.avanzar()
            self.prof -= 1
            if fallo:
                while self.tok().tipo != FIN and not self.es(")") and not self.es("{"):
                    self.avanzar()
                if self.es(")"):
                    self.avanzar()
            else:
                self._esperar(")", f"para cerrar la cabecera de '{kw.lexema}'", ap)
        else:
            if self.es(":") or self.es("{") or self.tok().tipo == FIN:
                self.error(f"Falta la condición en '{kw.lexema}'", kw)
            else:
                nodo.agregar(self.parse_expresion())
                while self.es(","):
                    self.avanzar()
                    nodo.agregar(self.parse_expresion())
                while self.kw() == "as":
                    self.avanzar()
                    nodo.agregar(self.parse_expresion())
        return nodo

    def parse_do(self):
        kw = self.avanzar()
        nodo = Nodo("Sentencia do-while", linea=kw.linea)
        nodo.agregar(self.parse_cuerpo(kw))
        n_err = len(self.errores)
        if self.kw() == "while":
            w = self.avanzar()
            nodo.agregar(self.parse_cabecera(w))
            self._cerrar(n_err, self.prev())
        else:
            self.error("Se esperaba 'while' después del cuerpo de 'do'")
        return nodo

    def parse_etiqueta(self):
        kw = self.avanzar()
        nodo = Nodo(f"Etiqueta {kw.lexema}", linea=kw.linea)
        if kw.lexema.lower() == "case":
            nodo.agregar(self.parse_expresion())
        self._esperar(":", f"después de '{kw.lexema}'")
        return nodo

    def parse_simple(self):
        kw = self.avanzar()
        n_err = len(self.errores)
        nodo = Nodo(f"Sentencia {kw.lexema}", linea=kw.linea)
        while not self._terminador():
            if self.tok().tipo == PR and self.kw() in SALTABLES:
                self.avanzar()
            elif self.es(",") or self.es("*"):
                self.avanzar()
            else:
                antes = self.i
                nodo.agregar(self.parse_expresion())
                if self.i == antes:
                    break
                if not (self._terminador() or self.es(",") or
                        (self.tok().tipo == PR and self.kw() in SALTABLES)):
                    break
        self._cerrar(n_err, self.prev())
        return nodo

    def parse_definicion(self):
        kw = self.avanzar()
        k = kw.lexema.lower()
        nodo = Nodo(f"Definición {kw.lexema}", linea=kw.linea)
        while self.es("*"):
            self.avanzar()
        if self.tok().tipo == ID:
            nodo.valor = self.avanzar().lexema
        elif k == "def":
            self.error("Se esperaba el nombre de la función después de 'def'", self.prev())
        if self.es("<"):                                   # genéricos <T>
            prof = 0
            while self.tok().tipo != FIN:
                if self.es("<"):
                    prof += 1
                elif self.es(">"):
                    prof -= 1
                elif self.es(">>"):
                    prof -= 2
                self.avanzar()
                if prof <= 0:
                    break
        if self.es("("):
            nodo.agregar(self.parse_parametros())
        while not (self.es("{") or self.es(":") or self.es(";") or self.es("}")
                   or self.tok().tipo == FIN):
            t = self.tok()
            if t.nl_antes and not self.exigir_pyc:
                break
            if t.tipo in (ID, PR) or (t.tipo in (OP, DEL) and t.lexema in
                                      (",", ".", "->", "<", ">", "?", "&", "*", "(", ")",
                                       "[", "]", "::")):
                self.avanzar()
            else:
                self.error(f"Cabecera de '{kw.lexema}' no válida: símbolo {self.desc(t)}")
                self._sincronizar()
                return nodo
            if self.es(":") and k in ("class", "struct") and \
                    self.kw(1) in ("public", "private", "protected", "virtual"):
                self.avanzar()                              # herencia C++  class A : public B
        if self.es(";"):
            self.avanzar()
            return nodo
        if k == "enum" and self.es("{"):
            nodo.agregar(self.parse_lista_llaves())
        else:
            nodo.agregar(self.parse_cuerpo(kw))
        if self.es(";") and k in ("struct", "class", "enum", "union"):
            self.avanzar()
        return nodo

    def parse_lista_llaves(self):
        ap = self.avanzar()
        nodo = Nodo("Lista de enumeración", linea=ap.linea)
        guardado, self.prof = self.prof, 1
        while self.tok().tipo != FIN and not self.es("}"):
            antes = self.i
            nodo.agregar(self.parse_asignacion())
            if self.es(",") or self.es(";"):
                self.avanzar()
            elif not self.es("}"):
                break
            if self.i == antes:
                break
        self.prof = guardado
        self._esperar("}", "para cerrar la enumeración", ap)
        return nodo

    # ---------------- declaraciones ----------------
    def _fin_tipo(self, j):
        """Si en la posición j empieza un tipo (int, unsigned long, Foo*, List<int>...)
        devuelve el índice justo después; si no, None."""
        inicio = j
        while self._t(j).tipo == PR and \
                self._t(j).lexema.lower() in (TIPOS | MODIFICADORES):
            j += 1
        if j == inicio:
            if self._t(j).tipo != ID:
                return None
            consumir = True
        else:
            a, b = self._t(j), self._t(j + 1)
            consumir = a.tipo == ID and (b.tipo == ID or (
                b.tipo == OP and b.lexema in ("*", "&", "<") and
                self._t(j + 2).tipo in (ID, OP)))
        if consumir:
            j += 1
            while self._t(j).tipo == OP and self._t(j).lexema in (".", "::") \
                    and self._t(j + 1).tipo == ID:
                j += 2
            if self._t(j).tipo == OP and self._t(j).lexema == "<":
                prof, k = 0, j
                while k - j < 24:
                    x = self._t(k)
                    if x.tipo == OP and x.lexema == "<":
                        prof += 1
                    elif x.tipo == OP and x.lexema == ">":
                        prof -= 1
                    elif x.tipo == OP and x.lexema == ">>":
                        prof -= 2
                    elif x.tipo in (ID, PR) or x.lexema in (",", ".", "?", "[", "]", "*", "&"):
                        pass
                    else:
                        return None
                    k += 1
                    if prof <= 0:
                        break
                if prof != 0:
                    return None
                j = k
        while self._t(j).tipo == OP and self._t(j).lexema in ("*", "&", "&&"):
            j += 1
        while self._t(j).lexema == "[" and self._t(j + 1).lexema == "]":
            j += 2
        return j

    def es_declaracion(self):
        j = self._fin_tipo(self.i)
        if j is None or self._t(j).tipo != ID:
            return False
        sig = self._t(j + 1)
        return (sig.tipo == FIN or sig.nl_antes or
                (sig.tipo == PR and sig.lexema.lower() in ("of", "in")) or
                (sig.tipo in (OP, DEL, PYC) and sig.lexema in
                 ("=", ";", ",", "(", "[", ")", ":")))

    def parse_declaracion(self, cerrar=True):
        ini = self.tok()
        n_err = len(self.errores)
        j = self._fin_tipo(self.i)
        tipo = " ".join(t.lexema for t in self.toks[self.i:j])
        self.i = j
        nombre = self.tok()
        if cerrar and self.es("(", 1):                       # función
            self.avanzar()
            nodo = Nodo("Función", nombre.lexema, linea=ini.linea)
            nodo.agregar(Nodo("Tipo de retorno", tipo))
            nodo.agregar(self.parse_parametros())
            while self.tok().tipo == PR and self.kw() not in CONTROL_TODO:
                if self.kw() == "throws":
                    self.avanzar()
                    while self.tok().tipo == ID or self.es(","):
                        self.avanzar()
                else:
                    self.avanzar()
            if self.es(";"):
                self.avanzar()
                nodo.tipo = "Prototipo de función"
            elif self.es("{"):
                nodo.agregar(self.parse_bloque())
            else:
                self.error("Se esperaba '{' o ';' después de los parámetros de la función",
                           self.prev())
                self._sincronizar()
            return nodo
        nodo = Nodo("Declaración", tipo, linea=ini.linea)
        while True:
            while self.tok().tipo == OP and self.tok().lexema in ("*", "&"):
                self.avanzar()
            nom = self.tok()
            if nom.tipo != ID:
                self.error(f"Se esperaba un nombre de variable pero se encontró {self.desc(nom)}")
                break
            self.avanzar()
            d = Nodo("Variable", nom.lexema, linea=nom.linea)
            while self.es("["):
                ap = self.avanzar()
                self.prof += 1
                if not self.es("]"):
                    d.agregar(Nodo("Tamaño", hijos=[self.parse_expresion()]))
                self.prof -= 1
                self._esperar("]", "para cerrar la dimensión del arreglo", ap)
            if self.es("="):
                self.avanzar()
                d.agregar(Nodo("Inicialización", hijos=[self.parse_asignacion()]))
            nodo.agregar(d)
            if self.es(","):
                self.avanzar()
                continue
            break
        if cerrar:
            self._cerrar(n_err, self.prev())
        return nodo

    def parse_parametros(self):
        nodo = Nodo("Parámetros")
        ap = self.tok()
        if not self._esperar("(", "para abrir la lista de parámetros"):
            return nodo
        self.prof += 1
        fallo = False
        while self.tok().tipo != FIN and not self.es(")"):
            if self.es("{") or self.es(";") or self.es("}"):
                break
            antes = self.i
            while self.tok().tipo == OP and self.tok().lexema in ("*", "**", "...", "&"):
                self.avanzar()
            j = self._fin_tipo(self.i)
            if j is not None and self._t(j).tipo == ID:
                tipo = " ".join(t.lexema for t in self.toks[self.i:j])
                self.i = j
                p = Nodo("Parámetro", self.avanzar().lexema)
                if tipo:
                    p.agregar(Nodo("Tipo", tipo))
            elif self.tok().tipo in (ID, PR):
                p = Nodo("Parámetro", self.avanzar().lexema)
            else:
                self.error(f"Parámetro no válido: {self.desc(self.tok())}")
                fallo = True
                break
            while self.es("["):
                while self.tok().tipo != FIN and not self.es("]"):
                    self.avanzar()
                self.avanzar()
            if self.es(":"):
                self.avanzar()
                p.agregar(self.parse_asignacion())
            elif self.es("="):
                self.avanzar()
                p.agregar(Nodo("Valor por defecto", hijos=[self.parse_asignacion()]))
            nodo.agregar(p)
            if self.es(","):
                self.avanzar()
            elif not self.es(")"):
                self.error(f"Se esperaba ',' o ')' en la lista de parámetros pero se "
                           f"encontró {self.desc(self.tok())}")
                fallo = True
                break
            if self.i == antes:
                break
        self.prof -= 1
        if fallo:
            while self.tok().tipo != FIN and not (self.es(")") or self.es("{")
                                                  or self.es(";") or self.es("}")):
                self.avanzar()
            if self.es(")"):
                self.avanzar()
        else:
            self._esperar(")", "para cerrar la lista de parámetros", ap)
        return nodo

    # ---------------- expresiones ----------------
    def parse_expresion(self):
        return self.parse_asignacion()

    def parse_asignacion(self):
        izq = self.parse_ternario()
        t = self.tok()
        if t.tipo == OP and t.lexema in ASIGNACION and self._continua(t):
            self.avanzar()
            if t.lexema == "=>" and self.es("{"):
                der = self.parse_bloque()
            elif self._fin_operando():
                self.error(f"Falta el valor a la derecha de '{t.lexema}'", t)
                der = Nodo("Error")
            else:
                der = self.parse_asignacion()
            if t.lexema == "=>":
                return Nodo("Función flecha", "=>", [izq, der], t.linea)
            return Nodo("Asignación", t.lexema, [izq, der], t.linea)
        return izq

    def parse_ternario(self):
        cond = self.parse_binario(1)
        t = self.tok()
        if t.tipo == OP and t.lexema == "?" and self._continua(t):
            self.avanzar()
            a = self.parse_asignacion()
            self._esperar(":", "en el operador ternario '?:'")
            b = self.parse_asignacion()
            return Nodo("Operador ternario", "?:", [cond, a, b], t.linea)
        if self.kw() == "if" and self.sin_if == 0 and not t.nl_antes:     # a if c else b
            self.avanzar()
            c = self.parse_binario(1)
            if self.kw() == "else":
                self.avanzar()
                b = self.parse_asignacion()
                return Nodo("Expresión condicional", "if-else", [cond, c, b], t.linea)
            self.error("Se esperaba 'else' en la expresión condicional", self.tok())
            return Nodo("Expresión condicional", "if", [cond, c], t.linea)
        return cond

    def parse_binario(self, minprec):
        izq = self.parse_unario()
        while True:
            t = self.tok()
            if t.tipo not in (OP, PR):
                break
            op = t.lexema.lower() if t.tipo == PR else t.lexema
            extra = 0
            if t.tipo == PR and op == "not" and self.kw(1) == "in":
                op, extra = "not in", 1
            elif t.tipo == PR and op not in OPS_PALABRA:
                break
            prec = PRECEDENCIA.get(op)
            if prec is None or prec < minprec or not self._continua(t):
                break
            self.avanzar()
            for _ in range(extra):
                self.avanzar()
            if op == "is" and self.kw() == "not":
                self.avanzar()
                op = "is not"
            if self._fin_operando():
                self.error(f"Falta el operando derecho de '{op}'", t)
                der = Nodo("Error")
            else:
                der = self.parse_binario(prec if op == "**" else prec + 1)
            izq = Nodo("Operación binaria", op, [izq, der], t.linea)
        return izq

    def parse_unario(self):
        t = self.tok()
        if (t.tipo == OP and t.lexema in UNARIOS_OP) or \
                (t.tipo == PR and t.lexema.lower() in UNARIOS_PALABRA):
            self.avanzar()
            if self._fin_operando():
                self.error(f"Falta el operando después de '{t.lexema}'", t)
                return Nodo("Error")
            return Nodo("Operación unaria", t.lexema, [self.parse_unario()], t.linea)
        return self.parse_postfijo()

    def parse_postfijo(self):
        e = self.parse_primario()
        while True:
            t = self.tok()
            if t.tipo == FIN or not self._continua(t):
                break
            if self.es("("):
                e = self.parse_llamada(e)
            elif self.es("["):
                e = self.parse_indice(e)
            elif t.tipo == OP and t.lexema in (".", "->", "::", "?."):
                self.avanzar()
                n = self.tok()
                if n.tipo in (ID, PR) or (n.tipo == OP and n.lexema == "*"):
                    self.avanzar()
                    e = Nodo("Acceso", t.lexema, [e, Nodo("Miembro", n.lexema)], t.linea)
                else:
                    self.error(f"Se esperaba un nombre después de '{t.lexema}' pero se "
                               f"encontró {self.desc(n)}", n)
                    break
            elif t.tipo == OP and t.lexema in ("++", "--") and not t.nl_antes:
                self.avanzar()
                e = Nodo("Operación postfija", t.lexema, [e], t.linea)
            else:
                break
        return e

    def parse_llamada(self, f):
        ap = self.avanzar()
        self.prof += 1
        nodo = Nodo("Llamada", hijos=[f], linea=ap.linea)
        args = nodo.agregar(Nodo("Argumentos"))
        while self.tok().tipo != FIN and not self.es(")"):
            if self.es(";") or self.es("}"):
                break
            antes = self.i
            args.agregar(self.parse_asignacion())
            if self.es(","):
                self.avanzar()
            elif not self.es(")"):
                break
            if self.i == antes:
                break
        self.prof -= 1
        self._esperar(")", "para cerrar la llamada", ap)
        return nodo

    def parse_indice(self, e):
        ap = self.avanzar()
        self.prof += 1
        nodo = Nodo("Índice", hijos=[e], linea=ap.linea)
        while self.tok().tipo != FIN and not self.es("]") and not self.es(";") \
                and not self.es("}"):
            if self.es(":") or self.es(","):
                self.avanzar()
                continue
            antes = self.i
            nodo.agregar(self.parse_asignacion())
            if self.i == antes or not (self.es(":") or self.es(",") or self.es("]")):
                break
        self.prof -= 1
        self._esperar("]", "para cerrar el índice", ap)
        return nodo

    def _comprension(self, nodo):
        while self.kw() in ("for", "if"):
            k = self.avanzar()
            self.sin_if += 1
            nodo.agregar(Nodo(f"Comprensión {k.lexema}", hijos=[self.parse_expresion()]))
            self.sin_if -= 1

    def parse_primario(self):
        t = self.tok()
        k = self.kw()
        if t.tipo == NUM:
            self.avanzar()
            return Nodo("Número", t.lexema, linea=t.linea)
        if t.tipo == CAD:
            self.avanzar()
            return Nodo("Cadena", t.lexema, linea=t.linea)
        if t.tipo == ID:
            self.avanzar()
            return Nodo("Identificador", t.lexema, linea=t.linea)
        if t.tipo == PR:
            if k == "lambda":
                return self.parse_lambda()
            if k in ("function", "fn", "func", "fun"):
                return self.parse_definicion()
            if k in PALABRAS_DE_SENTENCIA or k in OPS_PALABRA - {"not"}:
                self.error(f"La palabra reservada '{t.lexema}' no puede usarse aquí, "
                           f"dentro de una expresión", t)
                self.avanzar()
                return Nodo("Error")
            self.avanzar()
            return Nodo("Literal" if k in LITERALES else "Palabra reservada", t.lexema,
                        linea=t.linea)
        if self.es("("):
            ap = self.avanzar()
            self.prof += 1
            nodo = Nodo("Agrupación", linea=ap.linea)
            if not self.es(")"):
                nodo.agregar(self.parse_expresion())
                while self.es(","):
                    self.avanzar()
                    if not self.es(")"):
                        nodo.agregar(self.parse_expresion())
            self.prof -= 1
            self._esperar(")", "para cerrar el paréntesis", ap)
            if (len(nodo.hijos) == 1 and nodo.hijos[0].tipo == "Palabra reservada"
                    and nodo.hijos[0].valor.lower() in TIPOS):
                s = self.tok()
                if not s.nl_antes and (s.tipo in (ID, NUM, CAD) or self.es("(")):
                    return Nodo("Conversión (cast)", nodo.hijos[0].valor,
                                [self.parse_unario()], ap.linea)
            return nodo
        if self.es("["):
            ap = self.avanzar()
            self.prof += 1
            nodo = Nodo("Lista", linea=ap.linea)
            while self.tok().tipo != FIN and not self.es("]"):
                if self.es(";") or self.es("}"):
                    break
                antes = self.i
                nodo.agregar(self.parse_asignacion())
                self._comprension(nodo)
                if self.es(","):
                    self.avanzar()
                elif not self.es("]"):
                    break
                if self.i == antes:
                    break
            self.prof -= 1
            self._esperar("]", "para cerrar la lista", ap)
            return nodo
        if self.es("{"):
            ap = self.avanzar()
            self.prof += 1
            nodo = Nodo("Literal de objeto / diccionario / conjunto", linea=ap.linea)
            while self.tok().tipo != FIN and not self.es("}"):
                if self.es(";"):
                    break
                antes = self.i
                clave = self.parse_asignacion()
                if self.es(":"):
                    self.avanzar()
                    nodo.agregar(Nodo("Par clave:valor", hijos=[clave, self.parse_asignacion()]))
                else:
                    nodo.agregar(clave)
                self._comprension(nodo)
                if self.es(","):
                    self.avanzar()
                elif not self.es("}"):
                    break
                if self.i == antes:
                    break
            self.prof -= 1
            self._esperar("}", "para cerrar el literal", ap)
            return nodo
        if t.tipo == FIN or t.lexema in (")", "]", "}", ";", ","):
            self.error(f"Se esperaba una expresión pero se encontró {self.desc(t)}",
                       t if t.tipo != FIN else self.prev())
            return Nodo("Error")
        self.error(f"Símbolo inesperado {self.desc(t)}", t)
        self.avanzar()
        return Nodo("Error")

    def parse_lambda(self):
        kw = self.avanzar()
        nodo = Nodo("Lambda", linea=kw.linea)
        while self.tok().tipo != FIN and not self.es(":"):
            if self.tok().tipo == ID:
                nodo.agregar(Nodo("Parámetro", self.avanzar().lexema))
            elif self.es(",") or self.es("*") or self.es("**"):
                self.avanzar()
            elif self.es("="):
                self.avanzar()
                nodo.agregar(self.parse_ternario())
            else:
                break
        self._esperar(":", "en la expresión lambda")
        nodo.agregar(self.parse_asignacion())
        return nodo


# --------------------------------------------------------------------------
# Fachada: léxico + sintáctico + reporte
# --------------------------------------------------------------------------
class AnalizadorCodigo:
    def __init__(self, codigo: str, punto_y_coma="auto", sensible_mayusculas=False):
        self.codigo = codigo
        self.punto_y_coma = punto_y_coma        # "auto" | True | False
        self.lexico = AnalizadorLexico(sensible_mayusculas)
        self.tokens: List[Token] = []
        self.arbol: Optional[Nodo] = None
        self.errores_lexicos: List[str] = []
        self.errores_sintacticos: List[tuple] = []

    def analizar(self):
        self.tokens = self.lexico.tokenizar(self.codigo)
        self.errores_lexicos = list(self.lexico.errores)
        try:
            sint = AnalizadorSintactico(self.tokens, self.punto_y_coma)
            self.arbol = sint.analizar()
            self.errores_sintacticos = sorted(sint.errores)
        except Exception as e:  # jamás abortar
            self.arbol = Nodo("Programa")
            self.errores_sintacticos = [(1, 1, f"Error interno: {type(e).__name__}")]
        return self

    def reporte(self, mostrar_comentarios=False) -> str:
        s = ["=" * 60, " ANÁLISIS LÉXICO", "=" * 60,
             AnalizadorLexico.tabla(self.tokens, mostrar_comentarios),
             f"\nTotal de tokens: {len([t for t in self.tokens if t.tipo != COM])}"]
        for e in self.errores_lexicos:
            s.append(f"  ⚠ {e}")
        s += ["", "=" * 60, " ANÁLISIS SINTÁCTICO", "=" * 60]
        s += self.arbol.dibujar() if self.arbol else []
        s.append("")
        if self.errores_sintacticos:
            s.append(f"✘ Se encontraron {len(self.errores_sintacticos)} error(es) sintáctico(s):")
            for l, c, m in self.errores_sintacticos:
                s.append(f"  Línea {l}, col {c}: {m}")
        else:
            s.append("✔ Sintaxis correcta: no se encontraron errores.")
        return "\n".join(s)


def leer_archivo(ruta):
    with open(ruta, "rb") as f:
        datos = f.read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return datos.decode(enc)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


# ==========================================================================
# INTERFAZ GRÁFICA
# ==========================================================================
sys.setrecursionlimit(10000)

# ------------------------------- colores -------------------------------
BG, PANEL, PANEL2 = "#0b1226", "#121c36", "#0e1730"
TXT, TXT2, ACENTO = "#e6edf7", "#8fa3c4", "#29b6f6"
OK, MAL = "#2ecc71", "#ff5252"

EJEMPLOS_VALIDOS = {
    "C: if y asignación": "If (a<10) {a++;}\na = (c+b) / 2;",
    "C: for con printf": 'for (a=0; a<10; a--) {\n    b = b + 10;\n    printf("El valor de b es: ");\n    printf("%d", b);\n}',
    "C: función main": '#include <stdio.h>\n\nint main(void) {\n    int x = 5, y;\n    if (x > 3) { y = x * 2; } else { y = 0; }\n    return y;\n}',
    "Python: función": 'def suma(a, b=2):\n    if a > b:\n        return a + b\n    else:\n        return [i * 2 for i in range(b)]\n\nprint(suma(3))',
    "JavaScript": 'const f = (a, b) => a + b;\nlet o = {x: 1, y: [1, 2, 3]};\nfor (const k of ks) { console.log(k); }',
}
EJEMPLOS_ERROR = {
    "b=b++10 (de la guía)": 'for (a=0; a<10; a--) {b=b++10;}',
    "Falta ';'": "int a = 5\nint b = 6;",
    "Paréntesis sin cerrar": "x = (4 + 5 * 2;",
    "Operador sin operando": "a = 4 + ;",
    "Llave sin cerrar": "if (a > 1) {\n    b = 2;",
    "Carácter raro": "a = 5 $ 3;\nb = #;",
}


def color_de(n):
    t = n.tipo
    if t == "Error":
        return "#c62828"
    if t in ("Número", "Cadena", "Literal"):
        return "#00838f"
    if t in ("Identificador", "Variable", "Parámetro", "Miembro"):
        return "#1e4fd8"
    if t.startswith("Operación") or t in ("Asignación", "Operador ternario",
                                          "Expresión condicional", "Función flecha"):
        return "#c2561a"
    if t.startswith(("Sentencia", "Definición", "Función", "Prototipo", "Bloque",
                     "Etiqueta", "Condición", "Cabecera", "Declaración", "Programa")):
        return "#6a3fb5"
    return "#37474f"


class App(tk.Tk):
    MAX_NODOS_DIBUJO = 1500

    def __init__(self):
        super().__init__()
        self.title("Analizador Léxico y Sintáctico")
        self.geometry("1280x860")
        self.minsize(900, 640)
        self.configure(bg=BG)
        self.resultado = None
        self.escala = 1.0
        self.pos = {}
        self.textos_nodo = {}
        self._estilos()
        self._construir()
        self.bind("<Control-Return>", lambda e: self.analizar())
        self.bind("<F5>", lambda e: self.analizar())
        self.editor.focus_set()

    # ------------------------------------------------------------ estilos
    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=TXT2,
                    padding=(16, 8), font=("Segoe UI", 10, "bold"))
        s.map("TNotebook.Tab", background=[("selected", ACENTO)],
              foreground=[("selected", "#04101f")])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TXT,
                    rowheight=24, borderwidth=0, font=("Consolas", 11))
        s.configure("Treeview.Heading", background=PANEL2, foreground=ACENTO,
                    font=("Segoe UI", 10, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", "#1e4fd8")])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=TXT, arrowcolor=ACENTO)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)],
              foreground=[("readonly", TXT)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", TXT)
        s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=BG,
                    arrowcolor=ACENTO)
        s.configure("Horizontal.TScrollbar", background=PANEL2, troughcolor=BG,
                    arrowcolor=ACENTO)

    def _boton(self, padre, texto, comando, principal=False):
        b = tk.Button(padre, text=texto, command=comando, relief="flat", cursor="hand2",
                      bg=ACENTO if principal else PANEL, fg="#04101f" if principal else TXT,
                      activebackground="#4fc3f7" if principal else "#1b2a50",
                      activeforeground="#04101f" if principal else TXT,
                      font=("Segoe UI", 11 if principal else 10, "bold"),
                      padx=22 if principal else 14, pady=8 if principal else 6, bd=0)
        return b

    # -------------------------------------------------------- construcción
    def _construir(self):
        tk.Label(self, text="ANALIZADOR LÉXICO Y SINTÁCTICO", bg=BG, fg=ACENTO,
                 font=("Segoe UI", 22, "bold")).pack(pady=(14, 4))
        tk.Label(self, text="Escribe o pega tu código y pulsa ANALIZAR  (atajo: Ctrl+Enter o F5)",
                 bg=BG, fg=TXT2, font=("Segoe UI", 10)).pack()

        # --- editor
        marco = tk.Frame(self, bg=ACENTO, padx=2, pady=2)
        marco.pack(fill="x", padx=24, pady=(10, 8))
        interior = tk.Frame(marco, bg=PANEL2)
        interior.pack(fill="both")
        self.editor = tk.Text(interior, height=6, bg=PANEL2, fg=TXT, insertbackground=ACENTO,
                              font=("Consolas", 13), relief="flat", undo=True, wrap="none",
                              padx=10, pady=8, selectbackground="#1e4fd8", tabs=("1c",))
        sy = ttk.Scrollbar(interior, orient="vertical", command=self.editor.yview)
        sx = ttk.Scrollbar(interior, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        self.editor.pack(side="left", fill="both", expand=True)
        self.editor.tag_configure("err", background="#5a1f2a")

        # --- barra de botones
        barra = tk.Frame(self, bg=BG)
        barra.pack(fill="x", padx=24, pady=(0, 8))
        self._boton(barra, "▶  ANALIZAR", self.analizar, True).pack(side="left")
        self._boton(barra, "Limpiar", self.limpiar).pack(side="left", padx=(10, 0))
        self._boton(barra, "Abrir archivo…", self.abrir).pack(side="left", padx=(10, 0))

        self.estado = tk.Label(barra, text="", bg=BG, fg=TXT2, font=("Segoe UI", 13, "bold"))
        self.estado.pack(side="right")

        sel = tk.Frame(self, bg=BG)
        sel.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(sel, text="Ejemplos válidos:", bg=BG, fg=TXT2).pack(side="left")
        self.cb_ok = ttk.Combobox(sel, values=list(EJEMPLOS_VALIDOS), state="readonly", width=24)
        self.cb_ok.set("Elegir…")
        self.cb_ok.pack(side="left", padx=(6, 18))
        self.cb_ok.bind("<<ComboboxSelected>>", lambda e: self._cargar(EJEMPLOS_VALIDOS, self.cb_ok))
        tk.Label(sel, text="Ejemplos con error:", bg=BG, fg=TXT2).pack(side="left")
        self.cb_err = ttk.Combobox(sel, values=list(EJEMPLOS_ERROR), state="readonly", width=24)
        self.cb_err.set("Elegir…")
        self.cb_err.pack(side="left", padx=(6, 18))
        self.cb_err.bind("<<ComboboxSelected>>", lambda e: self._cargar(EJEMPLOS_ERROR, self.cb_err))
        tk.Label(sel, text="Exigir ';':", bg=BG, fg=TXT2).pack(side="left")
        self.cb_pyc = ttk.Combobox(sel, values=["Automático", "Sí", "No"], state="readonly", width=11)
        self.cb_pyc.set("Automático")
        self.cb_pyc.pack(side="left", padx=6)

        # --- pestañas
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=24, pady=(0, 6))

        # Tokens
        f_tok = tk.Frame(self.nb, bg=BG)
        self.nb.add(f_tok, text="  Tokens (léxico)  ")
        self.tv_tok = ttk.Treeview(f_tok, columns=("n", "lex", "tipo", "pos"), show="headings")
        for c, t, w, a in (("n", "#", 60, "center"), ("lex", "Lexema", 320, "w"),
                           ("tipo", "Tipo", 320, "w"), ("pos", "Línea:Col", 110, "center")):
            self.tv_tok.heading(c, text=t)
            self.tv_tok.column(c, width=w, anchor=a)
        sb = ttk.Scrollbar(f_tok, orient="vertical", command=self.tv_tok.yview)
        self.tv_tok.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tv_tok.pack(fill="both", expand=True)

        # Árbol gráfico
        f_arb = tk.Frame(self.nb, bg=BG)
        self.nb.add(f_arb, text="  Árbol sintáctico  ")
        tb = tk.Frame(f_arb, bg=PANEL)
        tb.pack(fill="x")
        for t, c in (("–", lambda: self.zoom(1 / 1.2)), ("+", lambda: self.zoom(1.2)),
                     ("Ajustar", self.ajustar)):
            tk.Button(tb, text=t, command=c, bg=PANEL2, fg=TXT, relief="flat", bd=0,
                      font=("Segoe UI", 10, "bold"), padx=14, pady=4,
                      activebackground="#1b2a50", activeforeground=TXT,
                      cursor="hand2").pack(side="left", padx=(6, 0), pady=6)
        for txt, col in (("Identificador", "#1e4fd8"), ("Valor", "#00838f"),
                         ("Operación", "#c2561a"), ("Estructura", "#6a3fb5"),
                         ("Error", "#c62828")):
            tk.Label(tb, text="●", fg=col, bg=PANEL, font=("Segoe UI", 12)).pack(side="left", padx=(14, 0))
            tk.Label(tb, text=txt, fg=TXT2, bg=PANEL, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(tb, text="Clic: detalle · Ctrl+rueda: zoom · Arrastrar: mover", fg=TXT2,
                 bg=PANEL, font=("Segoe UI", 9)).pack(side="right", padx=10)
        cuerpo = tk.Frame(f_arb, bg=PANEL2)
        cuerpo.pack(fill="both", expand=True)
        self.cv = tk.Canvas(cuerpo, bg=PANEL2, highlightthickness=0)
        cy = ttk.Scrollbar(cuerpo, orient="vertical", command=self.cv.yview)
        cx = ttk.Scrollbar(cuerpo, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=cy.set, xscrollcommand=cx.set)
        cy.pack(side="right", fill="y")
        cx.pack(side="bottom", fill="x")
        self.cv.pack(fill="both", expand=True)
        self.detalle = tk.Label(f_arb, text="", bg=BG, fg=TXT, anchor="w",
                                font=("Consolas", 10))
        self.detalle.pack(fill="x")
        self.cv.bind("<ButtonPress-1>", self._clic_cv)
        self.cv.bind("<B1-Motion>", lambda e: self.cv.scan_dragto(e.x, e.y, gain=1))
        self.cv.bind("<Control-MouseWheel>", lambda e: self.zoom(1.1 if e.delta > 0 else 1 / 1.1))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.cv.bind("<Shift-MouseWheel>", lambda e: self.cv.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.cv.bind("<Button-4>", lambda e: self.zoom(1.1) if e.state & 4 else self.cv.yview_scroll(-1, "units"))
        self.cv.bind("<Button-5>", lambda e: self.zoom(1 / 1.1) if e.state & 4 else self.cv.yview_scroll(1, "units"))

        # Árbol texto
        f_txt = tk.Frame(self.nb, bg=BG)
        self.nb.add(f_txt, text="  Árbol (texto)  ")
        self.txt_arbol = tk.Text(f_txt, bg=PANEL, fg=TXT, font=("Consolas", 11), relief="flat",
                                 wrap="none", state="disabled", padx=10, pady=8)
        sy2 = ttk.Scrollbar(f_txt, orient="vertical", command=self.txt_arbol.yview)
        sx2 = ttk.Scrollbar(f_txt, orient="horizontal", command=self.txt_arbol.xview)
        self.txt_arbol.configure(yscrollcommand=sy2.set, xscrollcommand=sx2.set)
        sy2.pack(side="right", fill="y")
        sx2.pack(side="bottom", fill="x")
        self.txt_arbol.pack(fill="both", expand=True)

        # Errores
        f_err = tk.Frame(self.nb, bg=BG)
        self.nb.add(f_err, text="  Errores  ")
        self.tv_err = ttk.Treeview(f_err, columns=("fase", "lin", "col", "msg"), show="headings")
        for c, t, w, a in (("fase", "Fase", 100, "center"), ("lin", "Línea", 70, "center"),
                           ("col", "Col", 70, "center"), ("msg", "Mensaje", 900, "w")):
            self.tv_err.heading(c, text=t)
            self.tv_err.column(c, width=w, anchor=a)
        self.tv_err.pack(fill="both", expand=True)
        self.tv_err.bind("<<TreeviewSelect>>", self._ir_a_error)

        self.resumen = tk.Label(self, text="", bg=PANEL2, fg=TXT2, anchor="w",
                                font=("Consolas", 10), padx=12, pady=6)
        self.resumen.pack(fill="x", padx=24, pady=(0, 12))

    # ------------------------------------------------------------ acciones
    def _cargar(self, dic, cb):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", dic[cb.get()])
        self.analizar()

    def limpiar(self):
        self.editor.delete("1.0", "end")
        self.editor.tag_remove("err", "1.0", "end")
        for tv in (self.tv_tok, self.tv_err):
            tv.delete(*tv.get_children())
        self.cv.delete("all")
        self.txt_arbol.configure(state="normal")
        self.txt_arbol.delete("1.0", "end")
        self.txt_arbol.configure(state="disabled")
        self.estado.configure(text="", fg=TXT2)
        self.resumen.configure(text="")
        self.detalle.configure(text="")
        self.cb_ok.set("Elegir…")
        self.cb_err.set("Elegir…")
        self.editor.focus_set()

    def abrir(self):
        ruta = filedialog.askopenfilename(title="Abrir código fuente")
        if not ruta:
            return
        try:
            codigo = leer_archivo(ruta)
        except Exception as e:
            messagebox.showerror("No se pudo abrir", str(e))
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", codigo)
        self.analizar()

    def analizar(self):
        codigo = self.editor.get("1.0", "end-1c")
        if not codigo.strip():
            self.estado.configure(text="Escribe o pega algo de código primero", fg=TXT2)
            return
        modo = {"Automático": "auto", "Sí": True, "No": False}[self.cb_pyc.get()]
        r = AnalizadorCodigo(codigo, punto_y_coma=modo).analizar()
        self.resultado = r

        # tokens
        self.tv_tok.delete(*self.tv_tok.get_children())
        n = 0
        for t in r.tokens:
            if t.tipo == COM:
                continue
            n += 1
            lex = (t.lexema.splitlines() or [""])[0]
            self.tv_tok.insert("", "end", values=(n, lex[:60], t.descripcion, f"{t.linea}:{t.col}"))

        # errores
        self.tv_err.delete(*self.tv_err.get_children())
        self.editor.tag_remove("err", "1.0", "end")
        for m in r.errores_lexicos:
            mm = m.split(": ", 1)
            lin = col = ""
            if m.startswith("Línea"):
                try:
                    p = mm[0].replace("Línea", "").split(", col")
                    lin, col = p[0].strip(), p[1].strip()
                except Exception:
                    pass
            self.tv_err.insert("", "end", values=("Léxico", lin, col, mm[-1]))
        for l, c, m in r.errores_sintacticos:
            self.tv_err.insert("", "end", values=("Sintáctico", l, c, m))
        for iid in self.tv_err.get_children():
            lin = self.tv_err.item(iid, "values")[1]
            if str(lin).isdigit():
                self.editor.tag_add("err", f"{lin}.0", f"{lin}.end+1c")

        # árbol texto
        self.txt_arbol.configure(state="normal")
        self.txt_arbol.delete("1.0", "end")
        self.txt_arbol.insert("1.0", "\n".join(r.arbol.dibujar()))
        self.txt_arbol.configure(state="disabled")

        # árbol gráfico
        self.dibujar_arbol(r.arbol)

        total_err = len(r.errores_lexicos) + len(r.errores_sintacticos)
        if total_err == 0:
            self.estado.configure(text="✓ Sintaxis válida", fg=OK)
        else:
            self.estado.configure(text=f"✘ {total_err} error(es)", fg=MAL)
        self.resumen.configure(
            text=f"Tokens: {n}   ·   Nodos del árbol: {r.arbol.contar()}   ·   "
                 f"Errores léxicos: {len(r.errores_lexicos)}   ·   "
                 f"Errores sintácticos: {len(r.errores_sintacticos)}")
        self.nb.select(3 if total_err else 1)

    def _ir_a_error(self, _):
        sel = self.tv_err.selection()
        if not sel:
            return
        lin = self.tv_err.item(sel[0], "values")[1]
        if str(lin).isdigit():
            self.editor.see(f"{lin}.0")
            self.editor.mark_set("insert", f"{lin}.0")

    # --------------------------------------------------------- árbol gráfico
    @staticmethod
    def _etiquetas(n):
        arriba = n.tipo if len(n.tipo) <= 26 else n.tipo[:25] + "…"
        v = "" if n.valor in (None, "") else str(n.valor)
        v = v.replace("\n", " ")
        abajo = v if len(v) <= 24 else v[:23] + "…"
        return arriba, abajo

    def dibujar_arbol(self, raiz):
        self.cv.delete("all")
        self.pos, self.textos_nodo = {}, {}
        if raiz.contar() > self.MAX_NODOS_DIBUJO:
            self.cv.create_text(30, 30, anchor="nw", fill=TXT2, font=("Segoe UI", 12),
                                text=f"El árbol tiene {raiz.contar()} nodos: es demasiado grande "
                                     f"para dibujarlo.\nUsa la pestaña «Árbol (texto)».")
            return
        base = tkfont.Font(family="Segoe UI", size=9)
        anchos, sub = {}, {}
        GAP = 14

        def medir(n):
            a, b = self._etiquetas(n)
            anchos[id(n)] = max(base.measure(a), base.measure(b), 40) + 18
            if not n.hijos:
                sub[id(n)] = anchos[id(n)] + GAP
            else:
                for h in n.hijos:
                    medir(h)
                sub[id(n)] = max(anchos[id(n)] + GAP, sum(sub[id(h)] for h in n.hijos))

        def colocar(n, x0, prof):
            sw = sub[id(n)]
            if n.hijos:
                cx = x0 + (sw - sum(sub[id(h)] for h in n.hijos)) / 2
                for h in n.hijos:
                    colocar(h, cx, prof + 1)
                    cx += sub[id(h)]
                centro = (self.pos[id(n.hijos[0])][0] + self.pos[id(n.hijos[-1])][0]) / 2
            else:
                centro = x0 + sw / 2
            self.pos[id(n)] = (centro, prof * 78 + 40, anchos[id(n)], n)

        medir(raiz)
        colocar(raiz, 0, 0)
        self._redibujar(raiz)
        self.after(50, self.ajustar)

    def _redibujar(self, raiz=None):
        if raiz is None:
            if not self.resultado:
                return
            raiz = self.resultado.arbol
        if not self.pos:
            return
        e = self.escala
        self.cv.delete("all")
        self.textos_nodo = {}
        f1 = tkfont.Font(family="Segoe UI", size=max(5, int(round(8 * e))))
        f2 = tkfont.Font(family="Segoe UI", size=max(6, int(round(10 * e))), weight="bold")
        h = 40 * e
        nodos = list(self.pos.values())

        def lineas(n):
            x, y, w, _ = self.pos[id(n)]
            for hijo in n.hijos:
                hx, hy, hw, _ = self.pos[id(hijo)]
                self.cv.create_line(x * e, y * e + h / 2, hx * e, hy * e - h / 2,
                                    fill="#3a4b73", width=max(1, int(e)), smooth=True)
                lineas(hijo)
        lineas(raiz)
        for x, y, w, n in nodos:
            a, b = self._etiquetas(n)
            col = color_de(n)
            r = self.cv.create_rectangle((x - w / 2) * e, y * e - h / 2, (x + w / 2) * e,
                                         y * e + h / 2, fill=col, outline="#9ab", width=1)
            if b:
                t1 = self.cv.create_text(x * e, y * e - h * 0.22, text=a, fill="#cfe3ff", font=f1)
                t2 = self.cv.create_text(x * e, y * e + h * 0.18, text=b, fill="white", font=f2)
                ids = (r, t1, t2)
            else:
                t1 = self.cv.create_text(x * e, y * e, text=a, fill="white", font=f2)
                ids = (r, t1)
            desc = n.tipo + (f": {n.valor}" if n.valor not in (None, "") else "")
            if n.linea:
                desc += f"   (línea {n.linea})"
            for i in ids:
                self.textos_nodo[i] = desc
        bb = self.cv.bbox("all")
        if bb:
            cw = max(self.cv.winfo_width(), 300)
            ancho = bb[2] - bb[0]
            dx = max(30, (cw - ancho) / 2) - bb[0]
            self.cv.move("all", dx, 30 - bb[1])
            self.cv.configure(scrollregion=(0, 0, max(cw, ancho + dx + 30),
                                            bb[3] - bb[1] + 60))

    def zoom(self, factor):
        self.escala = max(0.2, min(3.0, self.escala * factor))
        self._redibujar()

    def ajustar(self):
        if not self.pos:
            return
        self.update_idletasks()
        xs = [x - w / 2 for x, _, w, _ in self.pos.values()]
        xe = [x + w / 2 for x, _, w, _ in self.pos.values()]
        ys = [y for _, y, _, _ in self.pos.values()]
        ancho, alto = max(xe) - min(xs) + 60, max(ys) + 100
        cw, ch = max(self.cv.winfo_width(), 300), max(self.cv.winfo_height(), 200)
        self.escala = max(0.25, min(1.6, cw / ancho, ch / alto))
        self._redibujar()
        self.cv.xview_moveto(0)
        self.cv.yview_moveto(0)

    def _clic_cv(self, e):
        self.cv.scan_mark(e.x, e.y)
        cur = self.cv.find_withtag("current")
        if cur and cur[0] in self.textos_nodo:
            self.detalle.configure(text="  Nodo → " + self.textos_nodo[cur[0]])


if __name__ == "__main__":
    try:                                    # nitidez en pantallas de Windows con escala
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App()
    if len(sys.argv) > 1:
        try:
            app.editor.insert("1.0", leer_archivo(sys.argv[1]))
            app.analizar()
        except Exception as e:
            messagebox.showerror("No se pudo abrir el archivo", str(e))
    app.mainloop()