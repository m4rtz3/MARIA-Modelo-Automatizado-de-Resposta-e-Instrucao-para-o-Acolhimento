'''
Limpeza das Bases (Etapa 1 do CRISP-DM)

Este script faz a primeira limpeza das bases de dados, conforme a Seção 2.4 do PGT.
Isso inclui:
  1. Filtrar dados por período (2015-2024).
  2. Aplicar filtros básicos (ex: sexo feminino, CIDs específicos para agressão).
  3. Remover dados duplicados.
  4. Padronizar formatos (datas, idades, sexo, raça/cor).
  5. Tratar idades muito fora do comum (outliers).
  6. Analisar dados faltantes (missingness) e gerar um relatório.
  7. Criar flags para colunas com muitos dados faltantes, sem apagar a informação.

Por que não imputar dados faltantes agora?
  A ideia, conforme o PGT (Seção 2.4), é que a falta de dados no SINAN não é aleatória
  e pode conter informações importantes. Por isso, este script cria *flags* de dados
  faltantes, mas não tenta preencher esses valores. A decisão de como lidar com eles
  (preencher, ignorar, etc.) será feita no Script 03, após uma análise mais profunda.

ARQUIVOS LIDOS:
  SINAN: VIOLBR{aa}.dbc
  SIM:   DO{UF}{aaaa}.dbc
  SIM:   RD{UF}{aa}{mm}.dbc

ARQUIVOS GERADOS (em dados_limpos/, ao lado deste script):
  sinan_violencia_limpo.csv
  sim_obitos_agressao_mulheres_limpo.csv
  RELATORIO_MISSINGNESS.csv     ← análise de % NaN por coluna em cada base
  RELATORIO_DEDUP.csv           ← quantos duplicados foram removidos

Os CSVs são salvos em dados_limpos ao lado deste script. O CSV do SINAN só é
substituído depois que todos os anos configurados tiverem sido processados.

REQUISITOS:
  pip install datasus-dbc dbfread pandas
'''

import argparse
import time
import json
import os
import hashlib
from pathlib import Path

# CONFIGURAÇÃO — AJUSTE AOS  PATHS LOCAIS
PATHS = {
    'SINAN': r"D:\PGT\bancos\SINAN",
    'SIM':   r"D:\PGT\bancos\SIM",
}

OUTPUT = Path(__file__).resolve().parent / "dados_limpos"
OUTPUT.mkdir(exist_ok=True)

ANO_INI = 2015
ANO_FIM = 2024

# CIDs de agressão (CID-10) — conforme literatura (Bordoni et al., 2021)
# X85-X99: Agressões com instrumentos diversos (envenenamento, enforcamento,
#          arma de fogo, instrumento cortante, perfurante, contundente etc.)
# Y00-Y09: Agressões por outros meios (força corporal, abuso sexual etc.)
CIDS_AGRESSAO = (
    [f"X{i:02d}" for i in range(85, 100)] +
    [f"Y{i:02d}" for i in range(0, 10)]
)
CIDS_SET = set(CIDS_AGRESSAO)

# Codificações de sexo feminino em cada base — variam por base e por ano
# (campos de texto livre históricos do DATASUS são heterogêneos)
SEXO_F_SINAN = {'F', '2', 'Feminino'}
SEXO_F_SIM   = {'2'}

# Outliers de idade — limites fisiologicamente plausíveis (Seção 2.4 PGT)
IDADE_MIN = 0
IDADE_MAX = 120

# Schemas-alvo — colunas relevantes pro modelo MARIA conforme Seção 2.5 PGT
# (4 grupos: histórico de violência, relacionais, demográficas, territoriais)
# Colunas inexistentes em arquivos antigos são ignoradas silenciosamente.
COLS_SINAN = [
    # IDs e contexto
    'NU_NOTIFIC', 'TP_NOT', 'ID_AGRAVO', 'DT_NOTIFIC', 'NU_ANO',
    # Geografia
    'SG_UF_NOT', 'ID_MUNICIP', 'SG_UF', 'ID_MN_RESI',
    # Demografia da vítima
    'DT_OCOR', 'CS_SEXO', 'NU_IDADE_N', 'CS_RACA', 'CS_ESCOL_N',
    'CS_GESTANT', 'SIT_CONJUG', 'ORIENT_SEX', 'IDENT_GEN',
    # Histórico/deficiências da vítima (preditores do PGT)
    'DEF_FISICA', 'DEF_MENTAL', 'TRAN_MENT', 'TRAN_COMP',
    # Características da agressão (preditores principais do PGT)
    'LOCAL_OCOR', 'OUT_VEZES',
    'VIOL_FISIC', 'VIOL_PSICO', 'VIOL_TORT', 'VIOL_SEXU', 'VIOL_TRAF',
    'VIOL_FINAN', 'VIOL_NEGLI', 'VIOL_INFAN', 'VIOL_LEGAL', 'VIOL_OUTR',
    'LES_AUTOP', 'CIRC_LESAO',
    # Meios de agressão (binários — substitui MEI_AGRESS que era texto)
    'AG_FORCA', 'AG_ENFOR', 'AG_OBJETO', 'AG_CORTE',
    'AG_QUENTE', 'AG_ENVEN', 'AG_FOGO', 'AG_AMEACA', 'AG_OUTROS',
    # Violência sexual (binários)
    'SEX_ASSEDI', 'SEX_ESTUPR', 'SEX_PUDOR', 'SEX_PORNO', 'SEX_EXPLO',
    # Agressor — NOMES CORRIGIDOS após verificação direta no DBC:
    #   AUTOR_ALCOO (11 chars) não existe; campo real é AUTOR_ALCO (10 chars, limite DBF)
    #   AUTOR_PARE não existe; o parentesco é representado por 20 flags binários REL_*
    'AUTOR_SEXO', 'AUTOR_ALCO', 'NUM_ENVOLV',
    # Parentesco do autor com a vítima (flags binárias 1=sim, 2=não)
    'REL_PAI', 'REL_MAE', 'REL_PAD', 'REL_MAD',
    'REL_CONJ', 'REL_EXCON',
    'REL_NAMO', 'REL_EXNAM',
    'REL_FILHO', 'REL_IRMAO',
    'REL_DESCO', 'REL_CONHEC',
    'REL_CUIDA', 'REL_PATRAO', 'REL_INST', 'REL_POL',
    'REL_PROPRI', 'REL_OUTROS',
    # Encaminhamentos da rede de proteção
    'ENC_SAUDE', 'ENC_DEAM', 'ENC_MULHER', 'ENC_CREAS', 'ENC_DELEG',
    # Motivação e evolução
    'VIOL_MOTIV', 'EVOLUCAO',
]
COLS_SIM = [
    'TIPOBITO', 'DTOBITO', 'DTNASC', 'IDADE', 'SEXO', 'RACACOR',
    'ESTCIV', 'ESC', 'CODMUNRES', 'LOCOCOR', 'CODMUNOCOR',
    'CAUSABAS', 'CAUSABAS_O', 'CIRCOBITO', 'ASSISTMED',
]

# UTILS
def log(icon, msg):
    print(f"  {icon} {msg}", flush=True)

def hdr(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}", flush=True)

class DBCReadError(RuntimeError):
    """Falha ao carregar um DBC, impedindo que ele seja marcado como concluído."""

def ler_dbc_filtrado(
    dbc_path, cols_keep=None, filtro_sexo=None, filtro_cid=None, strict_errors=False
):
    """Lê arquivos .dbc, descompacta (se necessário) e aplica filtros.
    Faz a leitura de forma otimizada para evitar problemas de memória com arquivos grandes.

    Args:
      dbc_path     : caminho do .dbc
      cols_keep    : colunas a manter (None = todas)
      filtro_sexo  : (nome_coluna, set_valores). Ex: ('SEXO', {'2'})
      filtro_cid   : lista de colunas onde testar CIDs de agressão.
                     Match positivo se QUALQUER coluna tiver CID válido.

    Returns:
      pd.DataFrame com registros filtrados (vazio se nenhum passou).
    """
    import dbfread
    import pandas as pd
    import tempfile

    dbc_path = Path(dbc_path)

    # Se já existir um .dbf ao lado do .dbc, usa diretamente (sem decompressão)
    sibling_dbf = dbc_path.with_suffix('.dbf')
    if sibling_dbf.exists():
        dbf_path = sibling_dbf
        _tmp_to_delete = None
    else:
        # Tenta decompressão via datasus_dbc
        try:
            import datasus_dbc
        except ImportError:
            log("!", f"  datasus_dbc não instalado e .dbf não encontrado para {dbc_path.name}. "
                     "Instale o Visual Studio Build Tools e execute: pip install datasus-dbc")
            if strict_errors:
                raise DBCReadError(f"datasus_dbc não está instalado para {dbc_path.name}")
            return pd.DataFrame()

        with tempfile.NamedTemporaryFile(suffix='.dbf', delete=False) as tmp:
            dbf_path = Path(tmp.name)
        _tmp_to_delete = dbf_path

        try:
            datasus_dbc.decompress(str(dbc_path), str(dbf_path))
        except Exception as e:
            log("!", f"  Erro descomprimindo {dbc_path.name}: {type(e).__name__}: {e}")
            try:
                dbf_path.unlink(missing_ok=True)
            except:
                pass
            if strict_errors:
                raise DBCReadError(
                    f"Erro descomprimindo {dbc_path.name}: {type(e).__name__}: {e}"
                ) from e
            return pd.DataFrame()

    sexo_col, sexo_vals = filtro_sexo if filtro_sexo else (None, None)
    registros = []
    try:
        for rec in dbfread.DBF(str(dbf_path), encoding='latin-1', raw=False):
            if sexo_col is not None and sexo_vals is not None:
                v = rec.get(sexo_col)
                if v is None or str(v).strip() not in sexo_vals:
                    continue
            if filtro_cid:
                tem_cid = False
                for col_cid in filtro_cid:
                    val = rec.get(col_cid)
                    if val is None:
                        continue
                    if str(val).strip()[:3].upper() in CIDS_SET:
                        tem_cid = True
                        break
                if not tem_cid:
                    continue
            if cols_keep:
                rec = {k: rec.get(k) for k in cols_keep if k in rec}
            registros.append(rec)
    except Exception as e:
        log("!", f"  Erro lendo {dbf_path.name}: {type(e).__name__}: {e}")
        if strict_errors:
            raise DBCReadError(
                f"Erro lendo {dbc_path.name}: {type(e).__name__}: {e}"
            ) from e
    finally:
        if _tmp_to_delete is not None:
            try:
                _tmp_to_delete.unlink(missing_ok=True)
            except:
                pass

    if not registros:
        return pd.DataFrame()
    return pd.DataFrame(registros)

def _resume_signature(dbcs, base, cols_keep, filtros):
    """Cria uma assinatura para invalidar checkpoints se fontes ou filtros mudarem."""
    arquivos = []
    for dbc in dbcs:
        stat = dbc.stat()
        arquivos.append({
            'path': str(dbc.resolve()),
            'size': stat.st_size,
            'mtime_ns': stat.st_mtime_ns,
        })
    conteudo = {
        'versao': 1,
        'base': base,
        'periodo': [ANO_INI, ANO_FIM],
        'colunas': cols_keep,
        'filtros': filtros,
        'arquivos': arquivos,
    }
    return hashlib.sha256(
        json.dumps(conteudo, sort_keys=True).encode('utf-8')
    ).hexdigest()

def _salvar_progresso(caminho, estado):
    temporario = caminho.with_name(f'{caminho.name}.tmp')
    temporario.write_text(
        json.dumps(estado, ensure_ascii=False, sort_keys=True),
        encoding='utf-8',
    )
    with temporario.open('r+b') as arquivo:
        os.fsync(arquivo.fileno())
    temporario.replace(caminho)

def _iniciar_csv_retomavel(csv_out, assinatura, colunas):
    """Retoma um CSV parcial no último arquivo confirmado no manifesto."""
    parcial = csv_out.with_name(f'{csv_out.stem}.parcial{csv_out.suffix}')
    progresso = csv_out.with_name(f'{csv_out.stem}.progresso.json')
    estado = None

    if progresso.exists():
        try:
            candidato = json.loads(progresso.read_text(encoding='utf-8'))
            if (
                candidato.get('signature') == assinatura
                and isinstance(candidato.get('processed'), dict)
            ):
                if (
                    candidato.get('complete') is True
                    and csv_out.exists()
                    and candidato.get('output_size') == csv_out.stat().st_size
                ):
                    return csv_out, progresso, candidato
                if parcial.exists():
                    tamanho = parcial.stat().st_size
                    deslocamento = candidato.get('offset')
                    if (
                        isinstance(deslocamento, int)
                        and 0 <= deslocamento <= tamanho
                    ):
                        with parcial.open('r+b') as arquivo:
                            arquivo.truncate(deslocamento)
                        estado = candidato
        except (OSError, ValueError, TypeError):
            estado = None

    if estado is None:
        parcial.unlink(missing_ok=True)
        estado = {
            'signature': assinatura,
            'offset': 0,
            'processed': {},
        }
        import pandas as pd
        pd.DataFrame(columns=colunas).to_csv(
            parcial, index=False, encoding='utf-8-sig'
        )
        with parcial.open('r+b') as arquivo:
            os.fsync(arquivo.fileno())
        estado['offset'] = parcial.stat().st_size
        _salvar_progresso(progresso, estado)
    else:
        log(".", f"Retomando: {len(estado['processed'])} arquivo(s) já concluído(s)")

    return parcial, progresso, estado

def _confirmar_arquivo_csv(parcial, progresso, estado, chave, df, metricas):
    """Confirma linhas e checkpoint em ordem segura contra interrupções."""
    if len(df):
        df.to_csv(
            parcial, mode='a', header=False, index=False, encoding='utf-8'
        )
        with parcial.open('r+b') as arquivo:
            os.fsync(arquivo.fileno())
    estado['offset'] = parcial.stat().st_size
    estado['processed'][chave] = metricas
    _salvar_progresso(progresso, estado)

def _finalizar_csv_retomavel(parcial, progresso, estado, csv_out):
    parcial.replace(csv_out)
    estado['complete'] = True
    estado['output_size'] = csv_out.stat().st_size
    _salvar_progresso(progresso, estado)

def _resultado_csv_concluido(csv_out, estado, base):
    if not estado.get('complete'):
        return None
    import pandas as pd
    stats = _resumo_progresso(estado)
    log(".", f"{base}: CSV completo já existente; reutilizando sem reprocessar.")
    amostra = pd.read_csv(csv_out, nrows=50000, encoding='utf-8-sig')
    return {
        'relatorio': relatorio_missingness(amostra, base),
        'stats': stats,
        'incompleto': False,
        'arquivos_processados': len(estado['processed']),
    }

def _resultado_csv_parcial(csv_parcial, estado, base, total_arquivos):
    """Cria relatórios com o progresso confirmado, sem tratar a base como concluída."""
    import pandas as pd
    stats = _resumo_progresso(estado)
    if stats['lidos']:
        amostra = pd.read_csv(csv_parcial, nrows=50000, encoding='utf-8-sig')
        relatorio = relatorio_missingness(amostra, base)
    else:
        relatorio = None
    return {
        'relatorio': relatorio,
        'stats': stats,
        'incompleto': True,
        'arquivos_processados': len(estado['processed']),
        'total_arquivos': total_arquivos,
    }

def _carregar_sinan_concluido():
    """Carrega resultado SINAN já concluído sem ler novamente os DBCs."""
    base_dir = Path(PATHS['SINAN'])
    csv_out = OUTPUT / "sinan_violencia_limpo.csv"
    progresso = csv_out.with_name(f'{csv_out.stem}.progresso.json')
    if not base_dir.exists() or not csv_out.exists() or not progresso.exists():
        return None

    selecionados = []
    for dbc in _glob_dbc(base_dir, "VIOLBR"):
        ano = extrair_ano(dbc.name, 'SINAN')
        if ano and ANO_INI <= ano <= ANO_FIM:
            selecionados.append(dbc)
    assinatura = _resume_signature(selecionados, 'SINAN', COLS_SINAN, {})

    try:
        estado = json.loads(progresso.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None

    if (
        estado.get('signature') != assinatura
        or estado.get('complete') is not True
        or estado.get('output_size') != csv_out.stat().st_size
    ):
        return None
    return _resultado_csv_concluido(csv_out, estado, 'SINAN')

def _resumo_progresso(estado):
    resumo = {'lidos': 0, 'dedup_removidos': 0, 'outliers_idade': 0, 'por_ano': {}}
    for item in estado['processed'].values():
        resumo['lidos'] += item['lidos']
        resumo['dedup_removidos'] += item['dedup_removidos']
        resumo['outliers_idade'] += item['outliers_idade']
        ano = item.get('ano')
        if ano is not None:
            resumo['por_ano'][ano] = resumo['por_ano'].get(ano, 0) + item['lidos']
    return resumo

def _glob_dbc(base_dir, prefixo):
    """Lista arquivos .dbc/.DBC sem duplicar (no Windows, o sistema é case-insensitive)."""
    vistos = {}
    for padrao in (f"{prefixo}*.dbc", f"{prefixo}*.DBC",
                   f"{prefixo}*.Dbc", f"{prefixo}*.dbC"):
        for p in base_dir.glob(padrao):
            chave = str(p).lower()   # no Windows, mesmo arquivo = mesma chave
            vistos[chave] = p
    return sorted(vistos.values())

def extrair_ano(nome_arquivo, base):
    """Extrai o ano (4 dígitos) do nome do .dbc.

    SINAN VIOLBR15.dbc       → 2015 (2 dígitos)
    SIM   DOAC2020.dbc       → 2020 (4 dígitos)
    SIM   RDAC1501.dbc       → 2015 (2 dígitos AA + 2 dígitos MM)
    """
    import re
    nome = nome_arquivo.upper().replace('.DBC', '').replace('.DBF', '')
    if base == 'SINAN':
        m = re.search(r'(\d{2})$', nome)
        if m:
            yy = int(m.group(1))
            return 2000 + yy if yy < 80 else 1900 + yy
    elif base == 'SIM':
        m = re.search(r'(\d{4})$', nome)
        if m:
            return int(m.group(1))
    elif base == 'SIM': # Caso SIM RDACAAXX.dbc
        m = re.search(r'(\d{2})(\d{2})$', nome)
        if m:
            yy = int(m.group(1))
            return 2000 + yy if yy < 80 else 1900 + yy
    return None

# PADRONIZAÇÃO — conforme Seção 2.4 do PGT
def padroniza_idade(df, col_idade):
    """Converte códigos etários DATASUS para anos e marca idades fora de [0, 120]."""
    import pandas as pd
    import numpy as np
    if col_idade not in df.columns:
        return df, 0

    # DATASUS: prefixos 1-5 indicam horas, dias, meses, anos e 100+ anos.
    serie = df[col_idade].astype(str).str.strip()

    def _decode(s):
        if pd.isna(s):
            return np.nan
        s = str(s).strip()
        if s.lower() in ('', 'nan', 'none'):
            return np.nan
        # Remove apenas o decimal artificial produzido por colunas numéricas.
        if s.endswith('.0'):
            s = s[:-2]
        try:
            if len(s) >= 3 and s[0] in '12345' and s[1:].isdigit():
                valor = int(s[1:])
                if s[0] == '1' and valor <= 23:
                    return valor / (24 * 365.25)
                if s[0] == '2' and valor <= 30:
                    return valor / 365.25
                if s[0] == '3' and valor <= 11:
                    return valor / 12
                if s[0] == '4' and valor <= IDADE_MAX:
                    return float(valor)
                if s[0] == '5' and valor + 100 <= IDADE_MAX:
                    return float(valor + 100)
                return np.nan
            # Fallback: tenta converter direto (caso já venha em anos)
            n = float(s)
            return n if 0 <= n <= IDADE_MAX else np.nan
        except (ValueError, TypeError):
            return np.nan

    df = df.copy()
    df[f'{col_idade}_anos'] = serie.map(_decode)
    outliers = df[f'{col_idade}_anos'].isna().sum() - df[col_idade].isna().sum()
    return df, max(outliers, 0)

def padroniza_data(df, col_data):
    """Converte data do DATASUS (DDMMAAAA) para o formato padrão AAAA-MM-DD."""
    import pandas as pd
    if col_data not in df.columns:
        return df, 0
    df = df.copy()
    serie = df[col_data].astype(str).str.strip()

    def _conv(s):
        # Força string — pandas 3.0 pode passar float/NaN direto pro map
        if s is None:
            return pd.NaT
        s = str(s).strip()
        # Remove sufixo .0 de floats (ex: '1012015.0')
        if s.endswith('.0'):
            s = s[:-2]
        if s.isdigit():
            if len(s) == 7:
                s = '0' + s   # recupera zero a esquerda
            if len(s) == 8:
                try:
                    return pd.to_datetime(s, format='%d%m%Y', errors='coerce')
                except Exception:
                    return pd.NaT
        # Fallback: tenta inferir formato
        return pd.to_datetime(s, errors='coerce')

    df[f'{col_data}_padr'] = serie.map(_conv)
    # Contagem simples de invalidas (datas que viraram NaT)
    invalidas = int(df[f'{col_data}_padr'].isna().sum())
    return df, invalidas

def padroniza_raca(df, col_raca, base):
    """Padroniza os códigos de raça/cor para o padrão do IBGE (1-5, 9).
       Isso é necessário porque SINAN e SIM usam codificações ligeiramente diferentes."""
    if col_raca not in df.columns:
        return df
    df = df.copy()

    # Codificação SIM usa código IBGE direto (1-5, 9). SINAN às vezes vem
    # como string descritiva ("Branca", "Parda"). Mapeia tudo pra IBGE.
    mapa_descritivo = {
        'BRANCA': '1', 'PRETA': '2', 'AMARELA': '3', 'PARDA': '4',
        'INDIGENA': '5', 'INDÍGENA': '5', 'IGNORADO': '9',
    }

    def _norm(v):
        if v is None:
            return None
        s = str(v).strip().upper()
        if s in ('', 'NAN', 'NONE'):
            return None
        if s in mapa_descritivo:
            return mapa_descritivo[s]
        if s in ('1', '2', '3', '4', '5', '9'):
            return s
        return '9'  # qualquer outra coisa → Ignorado

    df[f'{col_raca}_padr'] = df[col_raca].map(_norm)
    return df

# RELATÓRIOS — análise de qualidade (PGT seção 2.4)
def relatorio_missingness(df, base_nome):
    """Calcula e classifica a porcentagem de dados faltantes (NaN) por coluna:
       - Mais de 50% faltante: 'alta' (pode ser excluída ou gerar flag).
       - Entre 10% e 50% faltante: 'moderada' (considerar preenchimento e flag).
       - Menos de 10% faltante: 'baixa' (pode ser preenchida de forma simples).
       - 0% faltante: 'completa' (não precisa de tratamento).
    Isso segue a classificação da Seção 2.4 do PGT."""
    import pandas as pd
    linhas = []
    for col in df.columns:
        n = len(df)
        nan_count = df[col].isna().sum()
        # Trata também strings vazias e 'nan' como ausência
        if df[col].dtype == object:
            extra = (df[col].astype(str).str.strip().isin(['', 'nan', 'None'])).sum()
            nan_count += extra
        pct = nan_count / n * 100 if n > 0 else 0

        if pct == 0:
            classe = 'completa'
        elif pct < 10:
            classe = 'baixa'
        elif pct < 50:
            classe = 'moderada'
        else:
            classe = 'alta'

        linhas.append({
            'base': base_nome,
            'coluna': col,
            'n_total': n,
            'n_ausentes': nan_count,
            'pct_ausentes': round(pct, 2),
            'classe_missingness': classe,
            'estrategia_sugerida': {
                'completa': 'manter',
                'baixa': 'imputar (mediana/moda)',
                'moderada': 'imputar + flag de imputação',
                'alta': 'flag binário OU excluir',
            }[classe],
        })
    return pd.DataFrame(linhas)

def adiciona_flags_missingness(df, classe_alvo='alta', relatorio=None, base=None):
    """Cria flags binários '_faltava_{col}' para colunas com muitos dados faltantes (missingness alta).
    Isso ajuda a preservar a informação MNAR, conforme o PGT (Bordoni et al., 2021)."""
    if relatorio is None:
        return df
    df = df.copy()
    cols_alvo = relatorio[
        (relatorio['base'] == base) &
        (relatorio['classe_missingness'] == classe_alvo)
    ]['coluna'].tolist()
    for col in cols_alvo:
        if col in df.columns and not col.startswith('_'):
            df[f'_faltava_{col}'] = df[col].isna().astype(int)
    return df

# 1. SINAN — Notificações de violência (Viva/SINAN)
def limpar_sinan():
    base_dir = Path(PATHS['SINAN'])
    csv_out  = OUTPUT / "sinan_violencia_limpo.csv"
    hdr(f"1/2 SINAN ({ANO_INI}-{ANO_FIM}) — em {base_dir}")

    if not base_dir.exists():
        log("x", f"Pasta não existe: {base_dir}")
        return None

    dbcs = _glob_dbc(base_dir, "VIOLBR")
    log(".", f"Encontrados {len(dbcs)} arquivos VIOLBR*.dbc")

    selecionados = []
    for dbc in dbcs:
        ano = extrair_ano(dbc.name, 'SINAN')
        if ano and ANO_INI <= ano <= ANO_FIM:
            selecionados.append((dbc, ano))
    log(".", f"Período {ANO_INI}-{ANO_FIM}: {len(selecionados)} arquivo(s)")
    anos_encontrados = {ano for _, ano in selecionados}
    anos_sem_arquivo = sorted(set(range(ANO_INI, ANO_FIM + 1)) - anos_encontrados)
    if anos_sem_arquivo:
        log("x", "SINAN: faltam arquivos para o(s) ano(s): "
                 + ", ".join(map(str, anos_sem_arquivo)))
        return None
    log(".", "Arquivos por ano: " + ", ".join(
        f"{ano} ({sum(1 for _, ano_arquivo in selecionados if ano_arquivo == ano)})"
        for ano in sorted(anos_encontrados)
    ))

    assinatura = _resume_signature(
        [dbc for dbc, _ in selecionados], 'SINAN', COLS_SINAN, {}
    )
    colunas_saida = [
        *COLS_SINAN, 'ANO_REF', 'DT_NOTIFIC_padr', 'DT_OCOR_padr',
        'NU_IDADE_N_anos', 'CS_RACA_padr',
    ]
    csv_temporario, progresso, estado = _iniciar_csv_retomavel(
        csv_out, assinatura, colunas_saida
    )
    resultado_existente = _resultado_csv_concluido(csv_out, estado, 'SINAN')
    if resultado_existente is not None:
        return resultado_existente
    concluidos = estado['processed']
    if len(concluidos) == len(selecionados):
        log(".", "Todos os arquivos SINAN já estavam processados; finalizando CSV.")

    for dbc, ano in selecionados:
        chave = str(dbc.resolve())
        if chave in concluidos:
            continue
        log(".", f"Lendo {dbc.name}...")
        try:
            df = ler_dbc_filtrado(
                dbc, cols_keep=COLS_SINAN, strict_errors=True
            )
            n_id = dedup_removidos = 0
            if len(df):
                df['ANO_REF'] = ano
                df, _ = padroniza_data(df, 'DT_NOTIFIC')
                df, _ = padroniza_data(df, 'DT_OCOR')
                df, n_id = padroniza_idade(df, 'NU_IDADE_N')
                df = padroniza_raca(df, 'CS_RACA', 'SINAN')

                antes = len(df)
                if 'NU_NOTIFIC' in df.columns:
                    df = df.drop_duplicates(
                        subset=['NU_NOTIFIC', 'ANO_REF'], keep='first'
                    )
                else:
                    df = df.drop_duplicates()
                dedup_removidos = antes - len(df)
                df = df.reindex(columns=colunas_saida)

            metricas = {
                'ano': int(ano),
                'lidos': int(len(df)),
                'dedup_removidos': int(dedup_removidos),
                'outliers_idade': int(n_id),
            }
            _confirmar_arquivo_csv(
                csv_temporario, progresso, estado, chave, df, metricas
            )
        except (DBCReadError, OSError) as e:
            log("x", f"SINAN interrompido em {dbc.name}: {e}")
            log(".", f"Progresso preservado: {len(concluidos)} arquivo(s) concluído(s). "
                     "Rode novamente para retomar.")
            return None

        log("v", f"  {dbc.name}: {metricas['lidos']:,} registros (ano {ano}; "
                 f"{len(estado['processed'])}/{len(selecionados)} arquivos concluídos)")

    if len(estado['processed']) != len(selecionados):
        log("x", "SINAN incompleto; checkpoint preservado para continuar na próxima execução.")
        return None

    stats = _resumo_progresso(estado)
    if stats['lidos'] == 0:
        log("x", "SINAN: nenhum registro encontrado; CSV anterior preservado.")
        return None

    _finalizar_csv_retomavel(csv_temporario, progresso, estado, csv_out)
    log("v", f"SINAN LIMPO: {stats['lidos']:,} linhas")
    for ano, quantidade in sorted(stats['por_ano'].items()):
        log(".", f"  {ano}: {quantidade:,} registros")
    log(".", f"  Outliers de idade: {stats['outliers_idade']:,}")
    log(".", f"  Duplicados removidos: {stats['dedup_removidos']:,}")
    log(".", f"  Tamanho: {csv_out.stat().st_size/1048576:.1f} MB")

    import pandas as pd
    amostra_df = pd.read_csv(csv_out, nrows=50000, encoding='utf-8-sig')
    rel = relatorio_missingness(amostra_df, 'SINAN')
    return {
        'relatorio': rel,
        'stats': stats,
        'incompleto': False,
        'arquivos_processados': len(estado['processed']),
    }

# 2. SIM — Óbitos por agressão (mulheres)
def limpar_sim():
    base_dir = Path(PATHS['SIM'])
    csv_out  = OUTPUT / "sim_obitos_agressao_mulheres_limpo.csv"
    hdr(f"2/2 SIM ({ANO_INI}-{ANO_FIM}) — em {base_dir}")

    if not base_dir.exists():
        log("x", f"Pasta não existe: {base_dir}")
        return None

    dbcs = _glob_dbc(base_dir, "DO")
    log(".", f"Encontrados {len(dbcs)} arquivos DO*.dbc")

    selecionados = []
    for dbc in dbcs:
        ano = extrair_ano(dbc.name, 'SIM')
        if ano and ANO_INI <= ano <= ANO_FIM:
            selecionados.append((dbc, ano))
    log(".", f"Período {ANO_INI}-{ANO_FIM}: {len(selecionados)} arquivo(s)")

    assinatura = _resume_signature(
        [dbc for dbc, _ in selecionados],
        'SIM',
        COLS_SIM,
        {'sexo': sorted(SEXO_F_SIM), 'cid': ['CAUSABAS']},
    )
    colunas_saida = [
        *COLS_SIM, 'ANO_REF', 'UF', 'DTOBITO_padr', 'DTNASC_padr',
        'IDADE_anos', 'RACACOR_padr',
    ]
    csv_temporario, progresso, estado = _iniciar_csv_retomavel(
        csv_out, assinatura, colunas_saida
    )
    resultado_existente = _resultado_csv_concluido(csv_out, estado, 'SIM')
    if resultado_existente is not None:
        return resultado_existente
    concluidos = estado['processed']
    if concluidos:
        log(".", f"Retomando após {len(concluidos)}/{len(selecionados)} arquivos.")

    for i, (dbc, ano) in enumerate(selecionados, 1):
        chave = str(dbc.resolve())
        if chave in concluidos:
            continue
        uf = dbc.name[2:4].upper()
        log(".", f"Lendo {dbc.name} ({i}/{len(selecionados)})...")
        try:
            df = ler_dbc_filtrado(
                dbc, cols_keep=COLS_SIM,
                filtro_sexo=('SEXO', SEXO_F_SIM),
                filtro_cid=['CAUSABAS'],
                strict_errors=True,
            )
            n_id = dedup_removidos = 0
            if len(df):
                df['ANO_REF'] = ano
                df['UF'] = uf
                df, _ = padroniza_data(df, 'DTOBITO')
                df, _ = padroniza_data(df, 'DTNASC')
                df, n_id = padroniza_idade(df, 'IDADE')
                df = padroniza_raca(df, 'RACACOR', 'SIM')

                antes = len(df)
                if 'DTOBITO' in df.columns and 'CODMUNRES' in df.columns:
                    df = df.drop_duplicates(
                        subset=['DTOBITO', 'DTNASC', 'CODMUNRES', 'CAUSABAS'],
                        keep='first',
                    )
                else:
                    df = df.drop_duplicates()
                dedup_removidos = antes - len(df)
                df = df.reindex(columns=colunas_saida)

            metricas = {
                'ano': int(ano),
                'lidos': int(len(df)),
                'dedup_removidos': int(dedup_removidos),
                'outliers_idade': int(n_id),
            }
            _confirmar_arquivo_csv(
                csv_temporario, progresso, estado, chave, df, metricas
            )
        except (DBCReadError, OSError) as e:
            log("x", f"SIM interrompido em {dbc.name}: {e}")
            log(".", f"Progresso preservado: {len(concluidos)} arquivo(s) concluído(s). "
                     "Libere espaço em disco e rode novamente para retomar.")
            return _resultado_csv_parcial(
                csv_temporario, estado, 'SIM', len(selecionados)
            )

        if i % 30 == 0 or i == len(selecionados):
            stats_parciais = _resumo_progresso(estado)
            log(".", f"  {len(estado['processed'])}/{len(selecionados)} arquivos "
                     f"({stats_parciais['lidos']:,} registros)")

    if len(estado['processed']) != len(selecionados):
        log("x", "SIM incompleto; checkpoint preservado para continuar na próxima execução.")
        return _resultado_csv_parcial(
            csv_temporario, estado, 'SIM', len(selecionados)
        )

    stats = _resumo_progresso(estado)
    if stats['lidos'] == 0:
        log("!", "SIM: nenhum registro após filtros; CSV anterior preservado.")
        return None

    _finalizar_csv_retomavel(csv_temporario, progresso, estado, csv_out)
    log("v", f"SIM LIMPO: {stats['lidos']:,} linhas")
    log(".", f"  Outliers de idade: {stats['outliers_idade']:,}")
    log(".", f"  Duplicados removidos: {stats['dedup_removidos']:,}")
    log(".", f"  Tamanho: {csv_out.stat().st_size/1048576:.1f} MB")

    import pandas as pd
    amostra_df = pd.read_csv(csv_out, nrows=50000, encoding='utf-8-sig')
    rel = relatorio_missingness(amostra_df, 'SIM')
    return {
        'relatorio': rel,
        'stats': stats,
        'incompleto': False,
        'arquivos_processados': len(estado['processed']),
    }

# 3. SIM — Internações por agressão (mulheres)

# MAIN

def main(argv=None):
    parser = argparse.ArgumentParser(description="Limpeza das bases SINAN e SIM.")
    parser.add_argument(
        "--somente-sim",
        "--only-sim",
        action="store_true",
        help="Processa/retoma apenas o SIM e reutiliza o resultado SINAN já concluído.",
    )
    args = parser.parse_args(argv)

    print(f"""
Limpeza das Bases (Etapa 1 do CRISP-DM)
Período: {ANO_INI}-{ANO_FIM}

O que o script faz:
  - Filtra dados pelo período de {ANO_INI} a {ANO_FIM}.
  - Aplica filtros básicos (ex: sexo feminino, CIDs de agressão).
  - Padroniza datas, idades e raça/cor.
  - Identifica idades fora do comum (outliers).
  - Remove registros duplicados.
  - Gera um relatório de dados faltantes (RELATORIO_MISSINGNESS.csv).

O que o script NÃO faz (ainda):
  - Não preenche dados faltantes (isso é no Script 03).
  - Não junta as bases (também no Script 03).
  - Não cria features novas (isso é no Script 04).

Caminhos configurados:
  SINAN: {PATHS['SINAN']}
  SIM:   {PATHS['SIM']}
""", flush=True)

    # Verifica deps
    try:
        import dbfread, pandas
    except ImportError as e:
        log("x", f"Falta instalar: {e.name}")
        log("!", "  Rode: pip install dbfread pandas")
        return

    import pandas as pd

    t0 = time.time()
    if args.somente_sim:
        resultado_sinan = _carregar_sinan_concluido()
        if resultado_sinan is None:
            log("x", "Não foi possível reutilizar o SINAN: resultado concluído "
                     "ou checkpoint compatível não encontrado.")
            log(".", "Rode sem --somente-sim para processar/retomar o SINAN primeiro.")
            return
        log(".", "Modo somente SIM: SINAN será incluído nos relatórios pelo resultado salvo.")
        resultado_sim = limpar_sim()
    else:
        resultado_sinan = limpar_sinan()
        resultado_sim = limpar_sim()

    resultados = {
        'SINAN': resultado_sinan,
        'SIM':   resultado_sim,
    }

    # RELATÓRIOS CONSOLIDADOS
    hdr("RELATÓRIOS DE QUALIDADE (Seção 2.4 PGT)")

    rels = []
    for res in resultados.values():
        if res is None or res['relatorio'] is None:
            continue
        rel = res['relatorio'].copy()
        rel['status_base'] = 'PARCIAL' if res.get('incompleto') else 'COMPLETA'
        rel['arquivos_processados'] = res.get('arquivos_processados', 0)
        if res.get('incompleto'):
            rel['total_arquivos'] = res.get('total_arquivos', 0)
        rels.append(rel)
    if rels:
        rel_total = pd.concat(rels, ignore_index=True)
        rel_csv = OUTPUT / "RELATORIO_MISSINGNESS.csv"
        rel_total.to_csv(rel_csv, index=False, encoding='utf-8-sig')
        log("v", f"Relatório de missingness: {rel_csv}")

        # Sumário no console
        for base, res in resultados.items():
            if res is None:
                continue
            r = res['relatorio']
            if r is None:
                log("!", f"{base}: sem registros processados para calcular missingness.")
                continue
            situacao = "PARCIAL" if res.get('incompleto') else "COMPLETA"
            log(".", f"{base}: base {situacao}; "
                     f"{res.get('arquivos_processados', 0)} arquivo(s) processado(s)"
                     + (f" de {res.get('total_arquivos', 0)}" if res.get('incompleto') else ""))
            log(".", f"\n  ── {base} ──")
            for classe in ['alta', 'moderada', 'baixa', 'completa']:
                n = (r['classe_missingness'] == classe).sum()
                if n > 0:
                    log(".", f"    {classe:10s}: {n} coluna(s)")
            # Lista colunas com alta missingness (importantes pra decisão)
            altas = r[r['classe_missingness'] == 'alta']['coluna'].tolist()
            if altas:
                log("!", f"    🚨 ALTA (>50% ausentes): {', '.join(altas[:8])}"
                       + (f" ... (+{len(altas)-8})" if len(altas) > 8 else ""))

    # Estatísticas de dedup/outliers
    stats_csv = OUTPUT / "RELATORIO_DEDUP.csv"
    stats_data = []
    for base, res in resultados.items():
        if res is None:
            continue
        s = res['stats']
        stats_data.append({
            'base': base,
            'registros_finais': s['lidos'],
            'duplicados_removidos': s['dedup_removidos'],
            'outliers_idade_marcados': s['outliers_idade'],
            'status_base': 'PARCIAL' if res.get('incompleto') else 'COMPLETA',
            'arquivos_processados': res.get('arquivos_processados', 0),
            'total_arquivos': res.get('total_arquivos', res.get('arquivos_processados', 0)),
        })
    pd.DataFrame(stats_data).to_csv(stats_csv, index=False, encoding='utf-8-sig')
    log("v", f"Relatório de dedup/outliers: {stats_csv}")

    # RESUMO FINAL
    hdr("RESUMO FINAL")
    for base, res in resultados.items():
        status = (
            "PARCIAL"
            if res and res.get('incompleto')
            else "OK" if res
            else "FALHOU"
        )
        log("!" if status == "PARCIAL" else "v" if res else "x", f"{base}: {status}")

    print(f"\n  Tempo total: {(time.time()-t0)/60:.1f} min")
    print(f"\n  Arquivos gerados em {OUTPUT.resolve()}:")
    for f in sorted(OUTPUT.glob("*.csv")):
        if ".parcial." in f.name:
            continue
        print(f"    {f.name}  ({f.stat().st_size/1048576:.1f} MB)")

    print(f"""
  ────────────────────────────────────────────────────────────
  PRÓXIMOS PASSOS:

  1. Suba os CSVs para MyDrive/MARIA/dados_brutos/ (se ainda não estiverem lá)
  2. Abra RELATORIO_MISSINGNESS.csv e analise as colunas com
     missingness 'alta' — decida o que fazer com cada uma
     (excluir? flag binário?) antes de partir pro Script 03
  3. Script 03 (próximo): integração via código IBGE + imputação
  4. Script 04: feature engineering (Seção 2.5 PGT) + variável-alvo
  ────────────────────────────────────────────────────────────
""")

if __name__ == "__main__":
    main()