#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPILADOR UNIFICADO  —  MENÚ PRINCIPAL + 2 ANALIZADORES (todo en un solo archivo)

Uso:
    python CompiladorUnificado.py              -> abre el menú principal
    python CompiladorUnificado.py archivo.c    -> abre directo el analizador de código
                                                  con ese archivo (al cerrarlo vuelve al menú)

Opciones del menú:
    1) Analizador léxico y sintáctico de CÓDIGO (C, C++, Java, JavaScript, Python...)
       Tokens, árbol sintáctico gráfico y de texto, y lista de errores.
    2) Analizador sintáctico de EXPRESIONES ARITMÉTICAS
       Árbol sintáctico con valores, árbol de derivación, derivación paso a paso,
       tokens, gramática y evaluación del resultado.

Dentro de cada analizador, el botón «⬅ Menú» (o cerrar la ventana) vuelve al menú.
Atajos del menú: tecla 1, tecla 2, Esc para salir.
"""
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import List, Optional

sys.setrecursionlimit(10000)


class _CierraLimpio:
    """Mixin para ventanas raíz: al cerrar cancela los temporizadores `after` pendientes
    (animaciones, autoajustes) para que no se disparen luego, ya con la ventana destruida."""

    def destroy(self):
        try:
            for pendiente in self.tk.splitlist(self.tk.call("after", "info")):
                self.tk.call("after", "cancel", pendiente)
        except tk.TclError:
            pass
        super().destroy()



# ==========================================================================
#  PARTE 1 — ANALIZADOR LÉXICO Y SINTÁCTICO DE CÓDIGO
# ==========================================================================

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
class NodoCodigo:
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
    def analizar(self) -> NodoCodigo:
        raiz = NodoCodigo("Programa")
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
            return NodoCodigo("Sentencia vacía", linea=t.linea)
        if self.es("{"):
            return self.parse_bloque()
        if self.es("}"):
            self.error("Se esperaba una sentencia pero se encontró '}'")
            return NodoCodigo("Error")
        if self.es("@"):                      # anotación / decorador
            self.avanzar()
            n = NodoCodigo("Anotación", linea=t.linea)
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
                return NodoCodigo(f"Etiqueta {t.lexema}", linea=t.linea)
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
        nodo = NodoCodigo("Sentencia de expresión", linea=t.linea)
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
        nodo = NodoCodigo("Bloque", linea=ap.linea)
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
                nodo = NodoCodigo("Bloque (indentado)", linea=dp.linea)
                while (self.tok().tipo != FIN and self.tok().col > kw.col
                       and not self.es("}")):
                    self._sentencia_segura(nodo)
                if not nodo.hijos:
                    self.error(f"Se esperaba un bloque indentado después de ':'", dp)
                return nodo
            if self.tok().tipo == FIN or self.es("}"):
                self.error(f"Se esperaba el cuerpo de '{kw.lexema}' después de ':'", dp)
                return NodoCodigo("Error")
            return self.parse_sentencia()
        if self.es(";"):
            self.avanzar()
            return NodoCodigo("Sentencia vacía", linea=kw.linea)
        if self.tok().tipo == FIN or self.es("}"):
            self.error(f"Se esperaba el cuerpo de '{kw.lexema}'", self.prev())
            return NodoCodigo("Error")
        return self.parse_sentencia()

    def parse_control(self, continuacion=False):
        kw = self.avanzar()
        k = kw.lexema.lower()
        nodo = NodoCodigo(f"Sentencia {kw.lexema}", linea=kw.linea)
        if not continuacion and k in CONTINUACION:
            self.error(f"'{kw.lexema}' sin una sentencia 'if'/'try' previa", kw)
        if k in CONTROL_CON_CABECERA:
            nodo.agregar(self.parse_cabecera(kw))
        nodo.agregar(self.parse_cuerpo(kw))
        while self.kw() in CONTINUACION and (self.tok().col >= kw.col or not self.tok().nl_antes):
            nodo.agregar(self.parse_control(continuacion=True))
        return nodo

    def parse_cabecera(self, kw):
        nodo = NodoCodigo("Condición" if kw.lexema.lower() in ("if", "elif", "elsif", "while",
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
        nodo = NodoCodigo("Sentencia do-while", linea=kw.linea)
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
        nodo = NodoCodigo(f"Etiqueta {kw.lexema}", linea=kw.linea)
        if kw.lexema.lower() == "case":
            nodo.agregar(self.parse_expresion())
        self._esperar(":", f"después de '{kw.lexema}'")
        return nodo

    def parse_simple(self):
        kw = self.avanzar()
        n_err = len(self.errores)
        nodo = NodoCodigo(f"Sentencia {kw.lexema}", linea=kw.linea)
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
        nodo = NodoCodigo(f"Definición {kw.lexema}", linea=kw.linea)
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
        nodo = NodoCodigo("Lista de enumeración", linea=ap.linea)
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
            nodo = NodoCodigo("Función", nombre.lexema, linea=ini.linea)
            nodo.agregar(NodoCodigo("Tipo de retorno", tipo))
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
        nodo = NodoCodigo("Declaración", tipo, linea=ini.linea)
        while True:
            while self.tok().tipo == OP and self.tok().lexema in ("*", "&"):
                self.avanzar()
            nom = self.tok()
            if nom.tipo != ID:
                self.error(f"Se esperaba un nombre de variable pero se encontró {self.desc(nom)}")
                break
            self.avanzar()
            d = NodoCodigo("Variable", nom.lexema, linea=nom.linea)
            while self.es("["):
                ap = self.avanzar()
                self.prof += 1
                if not self.es("]"):
                    d.agregar(NodoCodigo("Tamaño", hijos=[self.parse_expresion()]))
                self.prof -= 1
                self._esperar("]", "para cerrar la dimensión del arreglo", ap)
            if self.es("="):
                self.avanzar()
                d.agregar(NodoCodigo("Inicialización", hijos=[self.parse_asignacion()]))
            nodo.agregar(d)
            if self.es(","):
                self.avanzar()
                continue
            break
        if cerrar:
            self._cerrar(n_err, self.prev())
        return nodo

    def parse_parametros(self):
        nodo = NodoCodigo("Parámetros")
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
                p = NodoCodigo("Parámetro", self.avanzar().lexema)
                if tipo:
                    p.agregar(NodoCodigo("Tipo", tipo))
            elif self.tok().tipo in (ID, PR):
                p = NodoCodigo("Parámetro", self.avanzar().lexema)
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
                p.agregar(NodoCodigo("Valor por defecto", hijos=[self.parse_asignacion()]))
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
                der = NodoCodigo("Error")
            else:
                der = self.parse_asignacion()
            if t.lexema == "=>":
                return NodoCodigo("Función flecha", "=>", [izq, der], t.linea)
            return NodoCodigo("Asignación", t.lexema, [izq, der], t.linea)
        return izq

    def parse_ternario(self):
        cond = self.parse_binario(1)
        t = self.tok()
        if t.tipo == OP and t.lexema == "?" and self._continua(t):
            self.avanzar()
            a = self.parse_asignacion()
            self._esperar(":", "en el operador ternario '?:'")
            b = self.parse_asignacion()
            return NodoCodigo("Operador ternario", "?:", [cond, a, b], t.linea)
        if self.kw() == "if" and self.sin_if == 0 and not t.nl_antes:     # a if c else b
            self.avanzar()
            c = self.parse_binario(1)
            if self.kw() == "else":
                self.avanzar()
                b = self.parse_asignacion()
                return NodoCodigo("Expresión condicional", "if-else", [cond, c, b], t.linea)
            self.error("Se esperaba 'else' en la expresión condicional", self.tok())
            return NodoCodigo("Expresión condicional", "if", [cond, c], t.linea)
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
                der = NodoCodigo("Error")
            else:
                der = self.parse_binario(prec if op == "**" else prec + 1)
            izq = NodoCodigo("Operación binaria", op, [izq, der], t.linea)
        return izq

    def parse_unario(self):
        t = self.tok()
        if (t.tipo == OP and t.lexema in UNARIOS_OP) or \
                (t.tipo == PR and t.lexema.lower() in UNARIOS_PALABRA):
            self.avanzar()
            if self._fin_operando():
                self.error(f"Falta el operando después de '{t.lexema}'", t)
                return NodoCodigo("Error")
            return NodoCodigo("Operación unaria", t.lexema, [self.parse_unario()], t.linea)
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
                    e = NodoCodigo("Acceso", t.lexema, [e, NodoCodigo("Miembro", n.lexema)], t.linea)
                else:
                    self.error(f"Se esperaba un nombre después de '{t.lexema}' pero se "
                               f"encontró {self.desc(n)}", n)
                    break
            elif t.tipo == OP and t.lexema in ("++", "--") and not t.nl_antes:
                self.avanzar()
                e = NodoCodigo("Operación postfija", t.lexema, [e], t.linea)
            else:
                break
        return e

    def parse_llamada(self, f):
        ap = self.avanzar()
        self.prof += 1
        nodo = NodoCodigo("Llamada", hijos=[f], linea=ap.linea)
        args = nodo.agregar(NodoCodigo("Argumentos"))
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
        nodo = NodoCodigo("Índice", hijos=[e], linea=ap.linea)
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
            nodo.agregar(NodoCodigo(f"Comprensión {k.lexema}", hijos=[self.parse_expresion()]))
            self.sin_if -= 1

    def parse_primario(self):
        t = self.tok()
        k = self.kw()
        if t.tipo == NUM:
            self.avanzar()
            return NodoCodigo("Número", t.lexema, linea=t.linea)
        if t.tipo == CAD:
            self.avanzar()
            return NodoCodigo("Cadena", t.lexema, linea=t.linea)
        if t.tipo == ID:
            self.avanzar()
            return NodoCodigo("Identificador", t.lexema, linea=t.linea)
        if t.tipo == PR:
            if k == "lambda":
                return self.parse_lambda()
            if k in ("function", "fn", "func", "fun"):
                return self.parse_definicion()
            if k in PALABRAS_DE_SENTENCIA or k in OPS_PALABRA - {"not"}:
                self.error(f"La palabra reservada '{t.lexema}' no puede usarse aquí, "
                           f"dentro de una expresión", t)
                self.avanzar()
                return NodoCodigo("Error")
            self.avanzar()
            return NodoCodigo("Literal" if k in LITERALES else "Palabra reservada", t.lexema,
                        linea=t.linea)
        if self.es("("):
            ap = self.avanzar()
            self.prof += 1
            nodo = NodoCodigo("Agrupación", linea=ap.linea)
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
                    return NodoCodigo("Conversión (cast)", nodo.hijos[0].valor,
                                [self.parse_unario()], ap.linea)
            return nodo
        if self.es("["):
            ap = self.avanzar()
            self.prof += 1
            nodo = NodoCodigo("Lista", linea=ap.linea)
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
            nodo = NodoCodigo("Literal de objeto / diccionario / conjunto", linea=ap.linea)
            while self.tok().tipo != FIN and not self.es("}"):
                if self.es(";"):
                    break
                antes = self.i
                clave = self.parse_asignacion()
                if self.es(":"):
                    self.avanzar()
                    nodo.agregar(NodoCodigo("Par clave:valor", hijos=[clave, self.parse_asignacion()]))
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
            return NodoCodigo("Error")
        self.error(f"Símbolo inesperado {self.desc(t)}", t)
        self.avanzar()
        return NodoCodigo("Error")

    def parse_lambda(self):
        kw = self.avanzar()
        nodo = NodoCodigo("Lambda", linea=kw.linea)
        while self.tok().tipo != FIN and not self.es(":"):
            if self.tok().tipo == ID:
                nodo.agregar(NodoCodigo("Parámetro", self.avanzar().lexema))
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
        self.arbol: Optional[NodoCodigo] = None
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
            self.arbol = NodoCodigo("Programa")
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

EJEMPLOS_CODIGO_VALIDOS = {
    "C: if y asignación": "If (a<10) {a++;}\na = (c+b) / 2;",
    "C: for con printf": 'for (a=0; a<10; a--) {\n    b = b + 10;\n    printf("El valor de b es: ");\n    printf("%d", b);\n}',
    "C: función main": '#include <stdio.h>\n\nint main(void) {\n    int x = 5, y;\n    if (x > 3) { y = x * 2; } else { y = 0; }\n    return y;\n}',
    "Python: función": 'def suma(a, b=2):\n    if a > b:\n        return a + b\n    else:\n        return [i * 2 for i in range(b)]\n\nprint(suma(3))',
    "JavaScript": 'const f = (a, b) => a + b;\nlet o = {x: 1, y: [1, 2, 3]};\nfor (const k of ks) { console.log(k); }',
}
EJEMPLOS_CODIGO_ERROR = {
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


class AppCodigo(_CierraLimpio, tk.Tk):
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
        self._boton(barra, "⬅  Menú", self.destroy).pack(side="left", padx=(10, 0))

        self.estado = tk.Label(barra, text="", bg=BG, fg=TXT2, font=("Segoe UI", 13, "bold"))
        self.estado.pack(side="right")

        sel = tk.Frame(self, bg=BG)
        sel.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(sel, text="Ejemplos válidos:", bg=BG, fg=TXT2).pack(side="left")
        self.cb_ok = ttk.Combobox(sel, values=list(EJEMPLOS_CODIGO_VALIDOS), state="readonly", width=24)
        self.cb_ok.set("Elegir…")
        self.cb_ok.pack(side="left", padx=(6, 18))
        self.cb_ok.bind("<<ComboboxSelected>>", lambda e: self._cargar(EJEMPLOS_CODIGO_VALIDOS, self.cb_ok))
        tk.Label(sel, text="Ejemplos con error:", bg=BG, fg=TXT2).pack(side="left")
        self.cb_err = ttk.Combobox(sel, values=list(EJEMPLOS_CODIGO_ERROR), state="readonly", width=24)
        self.cb_err.set("Elegir…")
        self.cb_err.pack(side="left", padx=(6, 18))
        self.cb_err.bind("<<ComboboxSelected>>", lambda e: self._cargar(EJEMPLOS_CODIGO_ERROR, self.cb_err))
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


# ==========================================================================
#  PARTE 2 — ANALIZADOR SINTÁCTICO DE EXPRESIONES ARITMÉTICAS
# ==========================================================================

# ======================================================================
#  NÚCLEO: léxico + sintaxis + árboles
# ======================================================================
NO_TERMINALES = {"Expresión", "Término", "Factor"}


class ErrorSintactico(Exception):
    def __init__(self, mensaje, pos, regla=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.pos = pos
        self.regla = regla


class NodoExpr:
    def __init__(self, etiqueta, hijos=None):
        self.etiqueta = etiqueta
        self.hijos = hijos or []


def tokenizar(texto):
    """Lista de (tipo, lexema, posición). Tipos: NUM, OP, LPAR, RPAR, EOF."""
    tokens, i, n = [], 0, len(texto)
    while i < n:
        c = texto[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or c == ".":
            ini, puntos = i, 0
            while i < n and (texto[i].isdigit() or texto[i] == "."):
                puntos += texto[i] == "."
                i += 1
            lex = texto[ini:i]
            if puntos > 1 or lex == ".":
                raise ErrorSintactico(f"Número mal formado '{lex}'", ini,
                                      "Análisis léxico (tokens)")
            tokens.append(("NUM", lex, ini))
        elif c in "+-*/":
            tokens.append(("OP", c, i)); i += 1
        elif c == "(":
            tokens.append(("LPAR", c, i)); i += 1
        elif c == ")":
            tokens.append(("RPAR", c, i)); i += 1
        else:
            raise ErrorSintactico(f"Carácter no válido '{c}'", i,
                                  "Análisis léxico (tokens)")
    tokens.append(("EOF", "", n))
    return tokens


class Parser:
    """Descenso recursivo. El árbol respeta las producciones originales
    (recursión por la izquierda resuelta con bucles → asociatividad izquierda)."""

    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def actual(self):
        return self.tokens[self.i]

    def avanzar(self):
        t = self.tokens[self.i]
        self.i += 1
        return t

    @staticmethod
    def desc(tok):
        return "el final de la expresión" if tok[0] == "EOF" else f"'{tok[1]}'"

    def parsear(self):
        arbol = self.expresion()
        tok = self.actual()
        if tok[0] != "EOF":
            if tok[0] == "RPAR":
                raise ErrorSintactico(
                    "Paréntesis de cierre ')' sin su '(' correspondiente", tok[2],
                    "Expresión (fin de la entrada)")
            raise ErrorSintactico(
                f"Token inesperado {self.desc(tok)}: se esperaba un operador o el final",
                tok[2], "Expresión (fin de la entrada)")
        return arbol

    def expresion(self):
        izq = NodoExpr("Expresión", [self.termino()])
        while self.actual()[0] == "OP" and self.actual()[1] in "+-":
            op = self.avanzar()
            der = self.termino()
            izq = NodoExpr("Expresión", [izq, NodoExpr(op[1]), der])
        return izq

    def termino(self):
        izq = NodoExpr("Término", [self.factor()])
        while self.actual()[0] == "OP" and self.actual()[1] in "*/":
            op = self.avanzar()
            der = self.factor()
            izq = NodoExpr("Término", [izq, NodoExpr(op[1]), der])
        return izq

    def factor(self):
        tok = self.actual()
        if tok[0] == "NUM":
            self.avanzar()
            return NodoExpr("Factor", [NodoExpr(tok[1])])
        if tok[0] == "LPAR":
            self.avanzar()
            if self.actual()[0] == "RPAR":
                raise ErrorSintactico("Paréntesis vacíos: falta una expresión dentro de '( )'",
                                      self.actual()[2], "Factor → ( Expresión )")
            interior = self.expresion()
            cierre = self.actual()
            if cierre[0] != "RPAR":
                raise ErrorSintactico(
                    f"Se esperaba ')' pero se encontró {self.desc(cierre)} "
                    f"(paréntesis sin cerrar)", cierre[2], "Factor → ( Expresión )")
            self.avanzar()
            return NodoExpr("Factor", [NodoExpr("("), interior, NodoExpr(")")])
        raise ErrorSintactico(
            f"Se esperaba un número o '(' pero se encontró {self.desc(tok)}",
            tok[2], "Factor → ( Expresión ) | número")


def parsear_texto(texto):
    if not texto.strip():
        raise ErrorSintactico("La expresión está vacía", 0)
    return Parser(tokenizar(texto)).parsear()


def a_ast(nodo):
    h = nodo.hijos
    if nodo.etiqueta in ("Expresión", "Término"):
        return a_ast(h[0]) if len(h) == 1 else NodoExpr(h[1].etiqueta, [a_ast(h[0]), a_ast(h[2])])
    return NodoExpr(h[0].etiqueta) if len(h) == 1 else a_ast(h[1])


def evaluar(n):
    if not n.hijos:
        return float(n.etiqueta)
    a, b = evaluar(n.hijos[0]), evaluar(n.hijos[1])
    if n.etiqueta == "+": return a + b
    if n.etiqueta == "-": return a - b
    if n.etiqueta == "*": return a * b
    if b == 0:
        raise ZeroDivisionError
    return a / b


def formato_num(x):
    return str(int(x)) if x == int(x) else f"{x:.6g}"


def pasos_derivacion(raiz):
    """Derivación más a la izquierda. Cada paso: forma, regla, ini, n."""
    forma = [raiz]
    pasos = [{"forma": [raiz.etiqueta], "regla": None, "ini": 0, "n": 1}]
    while True:
        idx = next((k for k, n in enumerate(forma) if n.etiqueta in NO_TERMINALES), None)
        if idx is None:
            break
        nodo = forma[idx]
        regla = nodo.etiqueta + " → " + " ".join(h.etiqueta for h in nodo.hijos)
        forma = forma[:idx] + nodo.hijos + forma[idx + 1:]
        pasos.append({"forma": [n.etiqueta for n in forma], "regla": regla,
                      "ini": idx, "n": len(nodo.hijos)})
    return pasos


def contar_nodos(n):
    return 1 + sum(contar_nodos(h) for h in n.hijos)


def ast_texto(n):
    if not n.hijos:
        return n.etiqueta
    return f"({ast_texto(n.hijos[0])} {n.etiqueta} {ast_texto(n.hijos[1])})"


def valor_texto(n):
    try:
        return formato_num(evaluar(n))
    except ZeroDivisionError:
        return "indefinido (división entre 0)"


def hojas(n):
    return [n.etiqueta] if not n.hijos else [x for h in n.hijos for x in hojas(h)]


def tipo_nodo(lab):
    if lab in NO_TERMINALES: return lab
    if lab in ("+", "-"): return "sum"
    if lab in ("*", "/"): return "mul"
    if lab in ("(", ")"): return "par"
    return "num"


# ======================================================================
#  APARIENCIA
# ======================================================================
EXP_BG, EXP_PANEL, CAMPO = "#0f172a", "#1e293b", "#0b1220"
FG, MUTED, ACCENT = "#e2e8f0", "#94a3b8", "#38bdf8"
EXP_OK, ERR, WARN, SEL = "#22c55e", "#ef4444", "#facc15", "#fde047"
CANVAS_BG = "#111c33"

# tipo -> (relleno, borde)
ESTILO = {
    "num":       ("#0e7490", "#22d3ee"),
    "sum":       ("#1d4ed8", "#60a5fa"),
    "mul":       ("#c2410c", "#fb923c"),
    "par":       ("#334155", "#94a3b8"),
    "Expresión": ("#5b21b6", "#a78bfa"),
    "Término":   ("#92400e", "#fbbf24"),
    "Factor":    ("#166534", "#86efac"),
}
TEXTO_COLOR = {
    "num": "#22d3ee", "sum": "#60a5fa", "mul": "#fb923c", "par": "#94a3b8",
    "Expresión": "#a78bfa", "Término": "#fbbf24", "Factor": "#86efac",
}
SLOT = 100  # ancho reservado por hoja (px lógicos)


def aclarar(hexcolor, d=28):
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(min(255, v + d) for v in (r, g, b))


def boton(master, texto, comando, bg, fg="#0f172a", size=11):
    b = tk.Button(master, text=texto, command=comando, bg=bg, fg=fg,
                  activebackground=aclarar(bg), activeforeground=fg, relief="flat",
                  bd=0, padx=16, pady=8, font=("Segoe UI", size, "bold"), cursor="hand2")
    b.bind("<Enter>", lambda e: b.config(bg=aclarar(bg)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


# ======================================================================
#  VISTA DE ÁRBOL (canvas con zoom, desplazamiento, animación y clics)
# ======================================================================
class VistaArbol(tk.Frame):
    def __init__(self, master, tipo, leyenda, mensaje_inicial):
        super().__init__(master, bg=EXP_PANEL)
        self.tipo = tipo                 # "ast" | "parse"
        self.items, self.ancho, self.prof = [], 0, 0
        self.escala = 1.0
        self.job = None
        self.sucio, self.animar_pend = False, False
        self.sep_y = 84 if tipo == "ast" else 62
        self.mensaje_inicial = mensaje_inicial

        barra = tk.Frame(self, bg=EXP_PANEL)
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))
        for txt, f in (("−", 0.85), ("+", 1.18)):
            boton(barra, txt, lambda f=f: self.zoom(f), "#334155", FG, 12).pack(side="left", padx=(0, 4))
        boton(barra, "Ajustar", lambda: self.ajustar(False), "#334155", FG, 10).pack(side="left", padx=(0, 14))
        for txt, col in leyenda:
            tk.Label(barra, text="●", fg=col, bg=EXP_PANEL, font=("Segoe UI", 13)).pack(side="left")
            tk.Label(barra, text=txt + "   ", fg=MUTED, bg=EXP_PANEL, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(barra, text="Clic: detalle  ·  Ctrl+rueda: zoom  ·  Arrastrar: mover",
                 fg="#64748b", bg=EXP_PANEL, font=("Segoe UI", 9)).pack(side="right")

        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0, cursor="fleur")
        sy = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        sx = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(10, 0))
        sy.grid(row=1, column=1, sticky="ns", padx=(0, 6))
        sx.grid(row=2, column=0, sticky="ew", padx=10)
        self.info = tk.Label(self, text="", fg=SEL, bg=EXP_PANEL, anchor="w",
                             font=("Consolas", 12, "bold"))
        self.info.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 8))
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        c = self.canvas
        c.bind("<ButtonPress-1>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B1-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        c.bind("<MouseWheel>", self._rueda)
        c.bind("<Button-4>", self._rueda)
        c.bind("<Button-5>", self._rueda)
        c.bind("<Configure>", self._al_cambiar_tamano)
        self.bind("<Map>", self._al_mostrar)
        self._cfg_job = None
        self.mostrar_mensaje(mensaje_inicial, MUTED)

    # ---------------- API pública ----------------
    def mostrar_mensaje(self, texto, color):
        self._cancelar()
        self.items = []
        self.sucio = False
        self.info.config(text="")
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 400), max(c.winfo_height(), 300)
        c.configure(scrollregion=(0, 0, w, h))
        c.create_text(w / 2, h / 2, text=texto, fill=color, justify="center",
                      font=("Segoe UI", 15, "bold"), width=max(300, w - 120), tags="ph")

    def set_tree(self, raiz, animar=True):
        items, cursor = [], [0.0]

        def rec(n, depth, padre):
            it = {"id": len(items), "nodo": n, "depth": depth, "padre": padre, "kids": [], "x": 0}
            items.append(it)
            if padre is not None:
                padre["kids"].append(it)
            for h in n.hijos:
                rec(h, depth + 1, it)
            if not it["kids"]:
                it["x"] = cursor[0] + SLOT / 2
                cursor[0] += SLOT
            else:
                it["x"] = (it["kids"][0]["x"] + it["kids"][-1]["x"]) / 2

        rec(raiz, 0, None)
        for it in items:
            n = it["nodo"]
            it["kind"] = tipo_nodo(n.etiqueta)
            if self.tipo == "ast":
                if n.hijos:
                    it["info"] = f"Subexpresión: {ast_texto(n)[1:-1]}   =   {valor_texto(n)}"
                    it["valor"] = valor_texto(n)
                else:
                    it["info"] = f"Número: {n.etiqueta}"
                    it["valor"] = None
            else:
                if n.etiqueta in NO_TERMINALES:
                    regla = n.etiqueta + " → " + " ".join(h.etiqueta for h in n.hijos)
                    txt = " ".join(hojas(n)).replace("( ", "(").replace(" )", ")")
                    it["info"] = f"{regla}      deriva:  {txt}"
                else:
                    it["info"] = f"Terminal (hoja): {n.etiqueta}"
        self.items, self.ancho = items, cursor[0]
        self.prof = max(i["depth"] for i in items)
        self.sucio, self.animar_pend = True, animar
        self.info.config(text="")
        if self.winfo_ismapped():
            self.after(20, lambda: self.ajustar(animar))

    # ---------------- zoom / eventos ----------------
    def zoom(self, f):
        self.escala = min(2.2, max(0.3, self.escala * f))
        self.dibujar(False)

    def ajustar(self, animar=False):
        if not self.items:
            return
        self.update_idletasks()
        cw = max(self.canvas.winfo_width(), 300)
        ch = max(self.canvas.winfo_height(), 250)
        s = min((cw - 40) / max(self.ancho, 1), (ch - 70) / (self.prof * self.sep_y + 60))
        self.escala = min(1.25, max(0.4, s))
        self.dibujar(animar)

    def _al_mostrar(self, _e):
        if self.sucio and self.items:
            self.after(40, lambda: self.ajustar(self.animar_pend))

    def _al_cambiar_tamano(self, _e):
        if not self.items or self.job:
            return
        if self._cfg_job:
            self.after_cancel(self._cfg_job)
        self._cfg_job = self.after(150, lambda: self.dibujar(False))

    def _rueda(self, e):
        arriba = (getattr(e, "num", 0) == 4) or (e.delta > 0 if e.num != 5 else False)
        if e.state & 0x4:
            self.zoom(1.1 if arriba else 0.9)
        elif e.state & 0x1:
            self.canvas.xview_scroll(-2 if arriba else 2, "units")
        else:
            self.canvas.yview_scroll(-2 if arriba else 2, "units")

    def _cancelar(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None

    # ---------------- dibujo ----------------
    def _dims(self, it):
        k = it["kind"]
        if self.tipo == "parse":
            return ("rect", 94, 32) if k in NO_TERMINALES else ("oval", 34, 34)
        return ("oval", 50, 50) if k in ("sum", "mul") else ("rect", 48, 40)

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
             x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(p, smooth=True, **kw)

    def dibujar(self, animar=False):
        c = self.canvas
        self._cancelar()
        c.delete("all")
        if not self.items:
            return
        self.sucio = False
        s = self.escala
        cw = max(c.winfo_width(), 300)
        ox = max(40, (cw - self.ancho * s) / 2)
        oy = 40
        estado = "hidden" if animar else "normal"
        pos = lambda it: (ox + it["x"] * s, oy + it["depth"] * self.sep_y * s)
        borde_linea = max(1, int(2 * s))

        # aristas (debajo de los nodos)
        for it in self.items:
            p = it["padre"]
            if p is None:
                continue
            px, py = pos(p)
            cx, cy = pos(it)
            py += self._dims(p)[2] * s / 2
            cy -= self._dims(it)[2] * s / 2
            my = (py + cy) / 2
            c.create_line(px, py, px, my, cx, my, cx, cy, smooth=True, fill="#64748b",
                          width=borde_linea, state=estado, tags=(f"e{it['id']}",))

        # nodos
        fuente = ("Segoe UI", max(7, int(11 * s)), "bold")
        fuente_v = ("Segoe UI", max(7, int(9 * s)), "bold")
        for it in self.items:
            x, y = pos(it)
            forma, w, h = self._dims(it)
            w, h = w * s, h * s
            fill, borde = ESTILO[it["kind"]]
            tg = (f"n{it['id']}", f"s{it['id']}", "nodo")
            if forma == "oval":
                c.create_oval(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill=fill,
                              outline=borde, width=borde_linea, state=estado, tags=tg)
            else:
                self._rrect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, 10 * s, fill=fill,
                            outline=borde, width=borde_linea, state=estado, tags=tg)
            c.create_text(x, y, text=it["nodo"].etiqueta, fill="white", font=fuente,
                          state=estado, tags=(f"n{it['id']}", "nodo"))
            if self.tipo == "ast" and it.get("valor") is not None:
                c.create_text(x + w / 2 + 5 * s, y, anchor="w", text="= " + it["valor"],
                              fill="#7dd3fc", font=fuente_v, state=estado,
                              tags=(f"n{it['id']}",))

        c.tag_bind("nodo", "<Button-1>", self._clic_nodo)
        W = max(cw, 2 * ox + self.ancho * s)
        H = 2 * oy + (self.prof * self.sep_y + 40) * s
        c.configure(scrollregion=(0, 0, W, H))
        c.xview_moveto(0)
        c.yview_moveto(0)

        if animar:
            delay = 70 if len(self.items) <= 45 else 25

            def paso(k):
                if k >= len(self.items):
                    self.job = None
                    return
                i = self.items[k]["id"]
                c.itemconfigure(f"e{i}", state="normal")
                c.itemconfigure(f"n{i}", state="normal")
                self.job = self.after(delay, lambda: paso(k + 1))

            paso(0)

    def _clic_nodo(self, _e):
        c = self.canvas
        i = next((int(m.group(1)) for t in c.gettags("current")
                  if (m := re.fullmatch(r"n(\d+)", t))), None)
        if i is None:
            return
        for it in self.items:                      # restaurar
            c.itemconfigure(f"s{it['id']}", outline=ESTILO[it["kind"]][1],
                            width=max(1, int(2 * self.escala)))

        def marcar(it, nivel):
            c.itemconfigure(f"s{it['id']}", outline=SEL, width=5 if nivel == 0 else 3)
            for k in it["kids"]:
                marcar(k, nivel + 1)

        it = self.items[i]
        marcar(it, 0)
        self.info.config(text=it["info"])


# ======================================================================
#  APLICACIÓN
# ======================================================================
EJEMPLOS_EXPR_VALIDOS = ["(4 + 5) * (6 - 3) + 2 * 7", "2 + 3 * 4", "(2 + 3) * 4",
                    "10 / (5 - 3) - 1", "8 - 3 - 2", "((1 + 2) * (3 + 4)) / 7"]
EJEMPLOS_EXPR_ERROR = ["5 + * 3", "2 / (3 - )", "(4 + 5", "4 + 5)", "3 4",
                  "* 5", "7 $ 2", "()", "8 /", "2 ** 3"]
NOMBRES_TOKEN = {"NUM": "Número", "OP": "Operador", "LPAR": "Paréntesis que abre",
                 "RPAR": "Paréntesis que cierra", "EOF": "Fin de la entrada"}

TEXTO_GRAMATICA = """GRAMÁTICA DE LAS EXPRESIONES ARITMÉTICAS

    Expresión  →  Expresión + Término
               |  Expresión - Término
               |  Término

    Término    →  Término * Factor
               |  Término / Factor
               |  Factor

    Factor     →  ( Expresión )
               |  número


CÓMO LEER LOS COLORES

    ■ Expresión   (morado)   suma y resta: menor precedencia
    ■ Término     (ámbar)    multiplicación y división: mayor precedencia
    ■ Factor      (verde)    número o expresión entre paréntesis
    ■ Operadores + -  (azul)      ■ Operadores * /  (naranja)
    ■ Números (turquesa)          ■ Paréntesis (gris)


¿POR QUÉ SE DETECTAN LOS ERRORES?

    El analizador lee de izquierda a derecha. Cuando espera un número o '('
    (regla Factor) y encuentra otra cosa, se detiene y marca la posición
    exacta del error. Así ocurre con  5 + * 3  y con  2 / (3 - ).
"""


class AppExpresiones(_CierraLimpio, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analizador Sintáctico — Árbol de Operaciones")
        self.geometry("1360x900")
        self.minsize(1000, 700)
        self.configure(bg=EXP_BG)
        self._estilos()
        self._construir()
        self.after(350, self.analizar)

    # ---------------- estilos ----------------
    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=EXP_BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
        s.configure("TNotebook.Tab", background=EXP_PANEL, foreground=MUTED, padding=(20, 10),
                    font=("Segoe UI", 11, "bold"), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", ACCENT)],
              foreground=[("selected", "#0f172a")])
        s.configure("Treeview", background=CAMPO, fieldbackground=CAMPO, foreground=FG,
                    rowheight=30, font=("Consolas", 12), borderwidth=0)
        s.configure("Treeview.Heading", background=EXP_PANEL, foreground=ACCENT,
                    font=("Segoe UI", 11, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", "#1e40af")])
        s.configure("TCombobox", fieldbackground=CAMPO, background=EXP_PANEL, foreground=FG,
                    arrowcolor=ACCENT, bordercolor="#334155", padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", CAMPO)],
              foreground=[("readonly", FG)], selectbackground=[("readonly", CAMPO)],
              selectforeground=[("readonly", FG)])
        for o in ("Vertical", "Horizontal"):
            s.configure(f"{o}.TScrollbar", background="#475569", troughcolor=CAMPO,
                        arrowcolor=MUTED, bordercolor=CAMPO, lightcolor="#475569",
                        darkcolor="#475569", relief="flat", gripcount=0)
            s.map(f"{o}.TScrollbar", background=[("active", ACCENT)])
        self.option_add("*TCombobox*Listbox.background", CAMPO)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", "#1e40af")
        self.option_add("*TCombobox*Listbox.font", ("Consolas", 11))

    # ---------------- interfaz ----------------
    def _construir(self):
        tk.Label(self, text="ANALIZADOR SINTÁCTICO", fg=ACCENT, bg=EXP_BG,
                 font=("Segoe UI", 22, "bold")).pack(pady=(8, 6))

        # --- entrada ---
        ent = tk.Frame(self, bg=EXP_BG)
        ent.pack(fill="x", padx=24)
        tk.Label(ent, text="Ingresa una expresión aritmética:", fg=FG, bg=EXP_BG,
                 font=("Segoe UI", 12)).pack(anchor="w")
        fila = tk.Frame(ent, bg=EXP_BG)
        fila.pack(fill="x", pady=(4, 8))
        self.var = tk.StringVar(value="(4 + 5) * (6 - 3) + 2 * 7")
        self.entry = tk.Entry(fila, textvariable=self.var, font=("Consolas", 20), bg=CAMPO,
                              fg="white", insertbackground="white", relief="flat",
                              highlightthickness=3, highlightbackground="#334155",
                              highlightcolor=ACCENT, selectbackground=ERR, selectforeground="white")
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.entry.bind("<Return>", lambda e: self.analizar())
        self.entry.bind("<KeyRelease>", lambda e: self._validar_vivo())
        self.badge = tk.Label(fila, text="", bg=EXP_BG, width=24, font=("Segoe UI", 11, "bold"))
        self.badge.pack(side="left", padx=(12, 0))

        botones = tk.Frame(ent, bg=EXP_BG)
        botones.pack(fill="x", pady=(0, 10))
        boton(botones, "▶  GENERAR ÁRBOL", self.analizar, ACCENT, size=12).pack(side="left")
        boton(botones, "Limpiar", self.limpiar, "#334155", FG, 11).pack(side="left", padx=8)
        boton(botones, "⬅  Menú", self.destroy, "#334155", FG, 11).pack(side="left")
        self.animar = tk.BooleanVar(value=True)
        tk.Checkbutton(botones, text="Animar", variable=self.animar, fg=FG, bg=EXP_BG,
                       selectcolor=CAMPO, activebackground=EXP_BG, activeforeground=FG,
                       font=("Segoe UI", 11), highlightthickness=0, bd=0).pack(side="left", padx=6)

        cb_err = ttk.Combobox(botones, values=EJEMPLOS_EXPR_ERROR, state="readonly", width=14,
                              font=("Consolas", 11))
        cb_err.set("Elegir…")
        cb_err.pack(side="right")
        cb_err.bind("<<ComboboxSelected>>", lambda e: self._cargar(cb_err.get()))
        tk.Label(botones, text="Ejemplos con error:", fg=MUTED, bg=EXP_BG,
                 font=("Segoe UI", 10)).pack(side="right", padx=(18, 6))
        cb_ok = ttk.Combobox(botones, values=EJEMPLOS_EXPR_VALIDOS, state="readonly", width=26,
                             font=("Consolas", 11))
        cb_ok.set("Elegir…")
        cb_ok.pack(side="right")
        cb_ok.bind("<<ComboboxSelected>>", lambda e: self._cargar(cb_ok.get()))
        tk.Label(botones, text="Ejemplos válidos:", fg=MUTED, bg=EXP_BG,
                 font=("Segoe UI", 10)).pack(side="right", padx=(18, 6))

        # --- resultado (abajo) ---
        self.res = tk.Text(self, height=6, bg=CAMPO, fg=FG, relief="flat", wrap="word",
                           font=("Consolas", 12), padx=14, pady=8, state="disabled",
                           highlightthickness=0)
        self.res.pack(side="bottom", fill="x", padx=24, pady=(6, 14))
        for tag, cfg in {
            "ok": dict(foreground=EXP_OK, font=("Segoe UI", 14, "bold")),
            "err": dict(foreground=ERR, font=("Segoe UI", 14, "bold")),
            "warn": dict(foreground=WARN),
            "mono": dict(foreground=FG),
            "muted": dict(foreground=MUTED),
            "res": dict(foreground="#7dd3fc", font=("Consolas", 14, "bold")),
            "malo": dict(foreground="white", background=ERR, font=("Consolas", 12, "bold")),
            "msg": dict(foreground="#fca5a5", font=("Consolas", 12, "bold")),
        }.items():
            self.res.tag_configure(tag, **cfg)

        # --- pestañas ---
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=24, pady=(4, 0))

        self.v_ast = VistaArbol(
            self.nb, "ast",
            [("Número", ESTILO["num"][1]), ("+ −", ESTILO["sum"][1]), ("* /", ESTILO["mul"][1])],
            "Escribe una expresión y pulsa GENERAR ÁRBOL")
        self.v_parse = VistaArbol(
            self.nb, "parse",
            [("Expresión", ESTILO["Expresión"][1]), ("Término", ESTILO["Término"][1]),
             ("Factor", ESTILO["Factor"][1]), ("Terminales", ESTILO["num"][1])],
            "Escribe una expresión y pulsa GENERAR ÁRBOL")
        self.nb.add(self.v_ast, text="  🌳 Árbol sintáctico  ")
        self.nb.add(self.v_parse, text="  🧬 Árbol de derivación  ")

        f_pasos = tk.Frame(self.nb, bg=EXP_PANEL)
        self.t_pasos = tk.Text(f_pasos, bg=CAMPO, fg=FG, relief="flat", font=("Consolas", 13),
                               padx=16, pady=12, state="disabled", wrap="none",
                               highlightthickness=0, spacing1=2)
        sy = ttk.Scrollbar(f_pasos, orient="vertical", command=self.t_pasos.yview)
        self.t_pasos.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y", padx=(0, 4), pady=6)
        self.t_pasos.pack(fill="both", expand=True, padx=(8, 0), pady=6)
        self.nb.add(f_pasos, text="  📜 Derivación paso a paso  ")
        self.t_pasos.tag_configure("titulo", foreground=ACCENT, font=("Segoe UI", 14, "bold"))
        self.t_pasos.tag_configure("num", foreground="#64748b")
        self.t_pasos.tag_configure("regla", foreground="#64748b", font=("Consolas", 11))
        self.t_pasos.tag_configure("vacio", foreground=MUTED, font=("Segoe UI", 14, "bold"))
        for k, col in TEXTO_COLOR.items():
            self.t_pasos.tag_configure("c_" + k, foreground=col)
        self.t_pasos.tag_configure("nuevo", background="#334155", font=("Consolas", 13, "bold"))

        f_tok = tk.Frame(self.nb, bg=EXP_PANEL)
        self.tabla = ttk.Treeview(f_tok, columns=("n", "tipo", "lex", "pos"), show="headings")
        for col, txt, w in (("n", "#", 60), ("tipo", "Tipo de token", 260),
                            ("lex", "Lexema", 160), ("pos", "Posición", 120)):
            self.tabla.heading(col, text=txt)
            self.tabla.column(col, width=w, anchor="center")
        self.tabla.tag_configure("a", background=CAMPO)
        self.tabla.tag_configure("b", background="#13203a")
        self.tabla.pack(fill="both", expand=True, padx=10, pady=10)
        self.nb.add(f_tok, text="  🔤 Tokens  ")

        f_gram = tk.Frame(self.nb, bg=EXP_PANEL)
        t_gram = tk.Text(f_gram, bg=CAMPO, fg=FG, relief="flat", font=("Consolas", 13),
                         padx=20, pady=14, highlightthickness=0)
        t_gram.insert("1.0", TEXTO_GRAMATICA)
        t_gram.configure(state="disabled")
        t_gram.pack(fill="both", expand=True, padx=10, pady=10)
        self.nb.add(f_gram, text="  📖 Gramática  ")

    # ---------------- acciones ----------------
    def _cargar(self, texto):
        self.var.set(texto)
        self.analizar()

    def limpiar(self):
        self.var.set("")
        self.badge.config(text="")
        self.entry.config(highlightbackground="#334155", highlightcolor=ACCENT)
        for v in (self.v_ast, self.v_parse):
            v.mostrar_mensaje("Escribe una expresión y pulsa GENERAR ÁRBOL", MUTED)
        self._texto(self.t_pasos, [("Aún no hay derivación.\n", "vacio")])
        self.tabla.delete(*self.tabla.get_children())
        self._texto(self.res, [])
        self.entry.focus_set()

    def _validar_vivo(self):
        t = self.var.get()
        if not t.strip():
            self.badge.config(text="")
            self.entry.config(highlightbackground="#334155", highlightcolor=ACCENT)
            return None
        try:
            parsear_texto(t)
            self.badge.config(text="✓ Sintaxis válida", fg=EXP_OK)
            self.entry.config(highlightbackground=EXP_OK, highlightcolor=EXP_OK)
            return True
        except ErrorSintactico as e:
            self.badge.config(text=f"✗ Error en posición {e.pos + 1}", fg=ERR)
            self.entry.config(highlightbackground=ERR, highlightcolor=ERR)
            return False

    @staticmethod
    def _texto(widget, partes):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        for txt, tag in partes:
            widget.insert("end", txt, tag)
        widget.config(state="disabled")

    def analizar(self):
        texto = self.var.get()
        self._validar_vivo()
        self.tabla.delete(*self.tabla.get_children())
        try:
            raiz = parsear_texto(texto)
        except ErrorSintactico as e:
            self._mostrar_error(texto, e)
            return

        ast = a_ast(raiz)
        anim = self.animar.get()
        self.v_ast.set_tree(ast, anim)
        self.v_parse.set_tree(raiz, anim)
        self._llenar_pasos(raiz)
        tokens = tokenizar(texto)
        self._llenar_tokens(tokens)

        partes = [("✓  EXPRESIÓN SINTÁCTICAMENTE CORRECTA\n", "ok"),
                  ("Expresión:  ", "muted"), (texto.strip() + "\n", "mono")]
        try:
            partes += [("Resultado:  ", "muted"),
                       (f"{texto.strip()} = {formato_num(evaluar(ast))}\n", "res")]
        except ZeroDivisionError:
            partes += [("Aviso: hay una división entre cero (error semántico, no sintáctico)\n", "warn")]
        partes += [(f"Nodos: árbol sintáctico {contar_nodos(ast)}  ·  árbol de derivación "
                    f"{contar_nodos(raiz)}  ·  tokens {len(tokens) - 1}\n", "muted")]
        self._texto(self.res, partes)
        self.nb.select(0)

    def _mostrar_error(self, texto, e):
        msg = "✗  No se puede construir el árbol\n\n" + e.mensaje
        self.v_ast.mostrar_mensaje(msg, "#fca5a5")
        self.v_parse.mostrar_mensaje(msg, "#fca5a5")
        self._texto(self.t_pasos, [("No hay derivación: la expresión tiene un error sintáctico.\n", "vacio")])
        try:
            self._llenar_tokens(tokenizar(texto))
        except ErrorSintactico:
            pass

        malo = texto[e.pos:e.pos + 1]
        if not malo or malo.isspace():
            malo = "▮"
        partes = [(f"✗  ERROR SINTÁCTICO  ·  posición {e.pos + 1}\n", "err"),
                  ("Expresión:  ", "muted"), (texto[:e.pos], "mono"), (malo, "malo"),
                  (texto[e.pos + 1:] + "\n", "mono"),
                  ("Detalle:    ", "muted"), (e.mensaje + "\n", "msg")]
        if e.regla:
            partes += [("Regla que falló:  ", "muted"), (e.regla + "\n", "mono")]
        partes += [("El analizador se detiene en el primer error encontrado.\n", "muted")]
        self._texto(self.res, partes)
        self.entry.focus_set()
        self.entry.icursor(e.pos)
        if e.pos < len(texto):
            self.entry.selection_range(e.pos, e.pos + 1)

    def _llenar_tokens(self, tokens):
        self.tabla.delete(*self.tabla.get_children())
        for k, (t, lex, pos) in enumerate(tokens):
            self.tabla.insert("", "end", values=(k + 1, NOMBRES_TOKEN[t], lex or "—", pos + 1),
                              tags=("a" if k % 2 == 0 else "b",))

    def _llenar_pasos(self, raiz):
        partes = [("Derivación más a la izquierda\n\n", "titulo")]
        for k, p in enumerate(pasos_derivacion(raiz)):
            partes.append((f"{k:>2}  ⇒  ", "num"))
            for j, lab in enumerate(p["forma"]):
                tags = ["c_" + tipo_nodo(lab)]
                if k > 0 and p["ini"] <= j < p["ini"] + p["n"]:
                    tags.append("nuevo")
                partes.append((lab + " ", tuple(tags)))
            partes.append(("\n", ""))
            if p["regla"]:
                partes.append((f"        regla: {p['regla']}\n", "regla"))
        self._texto(self.t_pasos, partes)


# ==========================================================================
#  MENÚ PRINCIPAL
# ==========================================================================
class MenuPrincipal(_CierraLimpio, tk.Tk):
    """Ventana de inicio. Tras cerrarse, `opcion` vale 'codigo', 'expresiones' o None."""

    OPCIONES = [
        ("codigo", "1", "ANALIZADOR DE CÓDIGO",
         "Léxico + sintáctico para C, C++, Java, JavaScript, Python...\n"
         "Tokens, árbol sintáctico y errores con línea y columna.", "#29b6f6"),
        ("expresiones", "2", "ANALIZADOR DE EXPRESIONES",
         "Expresiones aritméticas: ( 4 + 5 ) * 2\n"
         "Árbol sintáctico, árbol de derivación, derivación paso a paso y resultado.", "#a78bfa"),
    ]

    def __init__(self):
        super().__init__()
        self.opcion = None
        self.title("Compilador — Menú principal")
        self.configure(bg=BG)
        self.resizable(False, False)
        ancho, alto = 760, 480
        x = (self.winfo_screenwidth() - ancho) // 2
        y = max(0, (self.winfo_screenheight() - alto) // 3)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

        tk.Label(self, text="COMPILADOR", bg=BG, fg=ACENTO,
                 font=("Segoe UI", 30, "bold")).pack(pady=(28, 0))
        tk.Label(self, text="Elige qué quieres hacer", bg=BG, fg=TXT2,
                 font=("Segoe UI", 12)).pack(pady=(2, 18))

        for clave, tecla, titulo, texto, color in self.OPCIONES:
            self._tarjeta(clave, tecla, titulo, texto, color)

        salir = tk.Button(self, text="Salir   (Esc)", command=self.destroy, relief="flat",
                          bd=0, cursor="hand2", bg=PANEL, fg=TXT2, activebackground="#1b2a50",
                          activeforeground=TXT, font=("Segoe UI", 10, "bold"), padx=20, pady=7)
        salir.pack(pady=(14, 0))

        for clave, tecla, *_ in self.OPCIONES:
            self.bind(tecla, lambda e, c=clave: self._abrir(c))
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _tarjeta(self, clave, tecla, titulo, texto, color):
        marco = tk.Frame(self, bg=color, padx=2, pady=2, cursor="hand2")
        marco.pack(fill="x", padx=50, pady=7)
        cuerpo = tk.Frame(marco, bg=PANEL, padx=18, pady=14)
        cuerpo.pack(fill="both")
        fila = tk.Frame(cuerpo, bg=PANEL)
        fila.pack(fill="x")
        numero = tk.Label(fila, text=tecla, bg=color, fg="#04101f", width=3,
                          font=("Segoe UI", 18, "bold"))
        numero.pack(side="left", padx=(0, 16))
        col = tk.Frame(fila, bg=PANEL)
        col.pack(side="left", fill="x", expand=True)
        t = tk.Label(col, text=titulo, bg=PANEL, fg=TXT, anchor="w",
                     font=("Segoe UI", 14, "bold"))
        t.pack(fill="x")
        d = tk.Label(col, text=texto, bg=PANEL, fg=TXT2, anchor="w", justify="left",
                     font=("Segoe UI", 10))
        d.pack(fill="x", pady=(3, 0))

        widgets = (marco, cuerpo, fila, numero, col, t, d)

        def entrar(_e):
            for w in (cuerpo, fila, col, t, d):
                w.configure(bg="#1b2a50")

        def salir(_e):
            for w in (cuerpo, fila, col, t, d):
                w.configure(bg=PANEL)

        for w in widgets:
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", salir)
            w.bind("<Button-1>", lambda e, c=clave: self._abrir(c))

    def _abrir(self, clave):
        self.opcion = clave
        self.destroy()

    def elegir(self):
        self.mainloop()
        return self.opcion


def abrir_codigo(ruta=None):
    app = AppCodigo()
    if ruta:
        try:
            app.editor.insert("1.0", leer_archivo(ruta))
            app.analizar()
        except Exception as e:
            messagebox.showerror("No se pudo abrir el archivo", str(e))
    app.mainloop()


def main():
    try:                                    # nitidez en pantallas de Windows con escala
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    if len(sys.argv) > 1:
        abrir_codigo(sys.argv[1])
    while True:
        opcion = MenuPrincipal().elegir()
        if opcion == "codigo":
            abrir_codigo()
        elif opcion == "expresiones":
            AppExpresiones().mainloop()
        else:
            break


if __name__ == "__main__":
    main()