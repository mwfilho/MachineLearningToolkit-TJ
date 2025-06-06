from flask import Blueprint, jsonify, send_file, request, g
import os
import logging
from funcoes_mni import (
    retorna_processo,
    retorna_documento_processo,
    retorna_peticao_inicial_e_anexos
)
from utils import (
    extract_mni_data,
    extract_capa_processo,
    extract_all_document_ids
)
import tempfile

# Configuração de logger
logger = logging.getLogger(__name__)

# Cria o blueprint da API com prefixo /api/v1
api = Blueprint('api', __name__, url_prefix='/api/v1')


@api.before_request
def before_any_request():
    """
    Hook que roda antes de qualquer rota. Mantém apenas para log.
    """
    logger.debug(f"Recebendo request: {request.method} {request.url}")
    # Não há verificação de API Key aqui


def get_mni_credentials():
    """
    Obtém CPF e senha do MNI dos headers ou das variáveis de ambiente.
    Usado por todas as rotas que consultam o MNI.
    """
    cpf = request.headers.get('X-MNI-CPF') or os.environ.get('MNI_ID_CONSULTANTE')
    senha = request.headers.get('X-MNI-SENHA') or os.environ.get('MNI_SENHA_CONSULTANTE')
    return cpf, senha


@api.route('/processo/<num_processo>', methods=['GET'])
def get_processo(num_processo):
    """
    Consulta os dados básicos de um processo (sem listar documentos ou conteúdos).
    Usa CPF/Senha do MNI (header ou ambiente).
    Exemplo:
      GET /api/v1/processo/1234567-89.2024.8.17.0001
      Headers:
        X-MNI-CPF: 06293234456
        X-MNI-SENHA: Simb@280303
    """
    try:
        logger.debug(f"API: Consultando dados do processo {num_processo}")
        cpf, senha = get_mni_credentials()

        if not cpf or not senha:
            return jsonify({
                'erro': 'Credenciais MNI não fornecidas',
                'mensagem': 'Forneça os headers X-MNI-CPF e X-MNI-SENHA'
            }), 401

        resposta = retorna_processo(num_processo, cpf=cpf, senha=senha)
        if not resposta:
            return jsonify({
                'erro': 'Processo não encontrado',
                'mensagem': f'Não foi possível obter dados para o processo {num_processo}'
            }), 404

        # Extrai dados brutos do MNI e formata
        dados_brutos = extract_mni_data(resposta)
        dados_formatados = {
            'numero': dados_brutos.get('numero'),
            'classe': dados_brutos.get('classe'),
            'assunto': dados_brutos.get('assunto'),
            'valor_causa': dados_brutos.get('valor_causa'),
            'partes': dados_brutos.get('partes'),
            'movimentacoes': dados_brutos.get('movimentacoes'),
            # Adicione outros campos conforme necessário
        }
        return jsonify(dados_formatados)

    except Exception as e:
        logger.error(f"API: Erro ao consultar processo: {str(e)}", exc_info=True)
        return jsonify({
            'erro': str(e),
            'mensagem': 'Erro ao consultar processo'
        }), 500


@api.route('/processo/<num_processo>/documento/<id_documento>', methods=['GET'])
def get_documento(num_processo, id_documento):
    """
    Obtém o binário de um documento específico do processo.
    Uso:
      GET /api/v1/processo/<num_processo>/documento/<id_documento>
      Headers:
        X-MNI-CPF: 06293234456
        X-MNI-SENHA: Simb@280303
    """
    try:
        logger.debug(f"API: Baixando documento {id_documento} do processo {num_processo}")
        cpf, senha = get_mni_credentials()

        if not cpf or not senha:
            return jsonify({
                'erro': 'Credenciais MNI não fornecidas',
                'mensagem': 'Forneça os headers X-MNI-CPF e X-MNI-SENHA'
            }), 401

        conteudo = retorna_documento_processo(num_processo, id_documento, cpf, senha)
        if not conteudo:
            return jsonify({
                'erro': 'Documento não encontrado',
                'mensagem': f'ID {id_documento} não encontrado para o processo {num_processo}'
            }), 404

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(conteudo)
        tmp.flush()
        tmp.close()
        return send_file(tmp.name,
                         as_attachment=True,
                         attachment_filename=f'{id_documento}.pdf')

    except Exception as e:
        logger.error(f"API: Erro ao baixar documento: {str(e)}", exc_info=True)
        return jsonify({
            'erro': str(e),
            'mensagem': 'Erro ao baixar documento'
        }), 500


@api.route('/processo/<num_processo>/peticao-inicial', methods=['GET'])
def get_peticao_inicial(num_processo):
    """
    Retorna a petição inicial + anexos do processo.
    Uso:
      GET /api/v1/processo/<num_processo>/peticao-inicial
      Headers:
        X-MNI-CPF: 06293234456
        X-MNI-SENHA: Simb@280303
    """
    try:
        logger.debug(f"API: Consultando petição inicial do processo {num_processo}")
        cpf, senha = get_mni_credentials()

        if not cpf or not senha:
            return jsonify({
                'erro': 'Credenciais MNI não fornecidas',
                'mensagem': 'Forneça os headers X-MNI-CPF e X-MNI-SENHA'
            }), 401

        dados = retorna_peticao_inicial_e_anexos(num_processo, cpf, senha)
        if not dados:
            return jsonify({
                'erro': 'Petição inicial não encontrada',
                'mensagem': f'Não foi possível obter petição inicial para {num_processo}'
            }), 404

        return jsonify(dados)

    except Exception as e:
        logger.error(f"API: Erro ao consultar petição inicial: {str(e)}", exc_info=True)
        return jsonify({
            'erro': str(e),
            'mensagem': 'Erro ao consultar petição inicial'
        }), 500


@api.route('/processo/<num_processo>/documentos/ids', methods=['GET'])
def get_documentos_ids(num_processo):
    """
    Retorna uma lista única com todos os IDs de documentos do processo, incluindo vinculados,
    na ordem em que aparecem no processo.
    Uso:
      GET /api/v1/processo/<num_processo>/documentos/ids
      Headers:
        X-MNI-CPF: 06293234456
        X-MNI-SENHA: Simb@280303
    """
    try:
        logger.debug(f"API: Consultando lista de IDs de documentos do processo {num_processo}")
        cpf, senha = get_mni_credentials()

        if not cpf or not senha:
            return jsonify({
                'erro': 'Credenciais MNI não fornecidas',
                'mensagem': 'Forneça os headers X-MNI-CPF e X-MNI-SENHA'
            }), 401

        resposta = retorna_processo(num_processo, cpf=cpf, senha=senha)
        dados = extract_all_document_ids(resposta, num_processo=num_processo, cpf=cpf, senha=senha)
        return jsonify(dados)

    except Exception as e:
        logger.error(f"API: Erro ao consultar lista de IDs de documentos: {str(e)}", exc_info=True)
        return jsonify({
            'erro': str(e),
            'mensagem': 'Erro ao consultar lista de IDs de documentos'
        }), 500


@api.route('/processo/<num_processo>/capa', methods=['GET'])
def get_capa_processo(num_processo):
    """
    Retorna apenas os dados da capa do processo (sem documentos),
    incluindo dados básicos, assuntos, polos e movimentações.
    Uso:
      GET /api/v1/processo/<num_processo>/capa
      Headers:
        X-MNI-CPF: 06293234456
        X-MNI-SENHA: Simb@280303
    """
    try:
        logger.debug(f"API: Consultando capa do processo {num_processo}")
        cpf, senha = get_mni_credentials()

        if not cpf or not senha:
            return jsonify({
                'erro': 'Credenciais MNI não fornecidas',
                'mensagem': 'Forneça os headers X-MNI-CPF e X-MNI-SENHA'
            }), 401

        resposta = retorna_processo(num_processo, cpf=cpf, senha=senha, incluir_documentos=False)
        dados = extract_capa_processo(resposta)
        return jsonify(dados)

    except Exception as e:
        logger.error(f"API: Erro ao consultar capa do processo: {str(e)}", exc_info=True)
        return jsonify({
            'erro': str(e),
            'mensagem': 'Erro ao consultar capa do processo'
        }), 500
