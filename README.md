# Cath Unhas — site de unhas em gel

MVP funcional em Python/Flask + SQLite. Inclui catálogo, agendamento público, cadastro simples de clientes e painel administrativo.

## Windows — instalação
1. Instale Python 3.11 ou superior.
2. Extraia o ZIP e abra a pasta no terminal.
3. Execute:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   python app.py
   ```
4. Abra http://127.0.0.1:5000

## Acesso inicial ao painel
- URL: http://127.0.0.1:5000/login
- Usuário: `admin`
- Senha: `admin123`

**Antes de publicar na internet:** configure `ADMIN_USER`, `ADMIN_PASSWORD` e `SECRET_KEY` como variáveis de ambiente fortes. O agendamento neste MVP registra a solicitação e orienta confirmação pelo WhatsApp; integração de envio automático, pagamento online, disponibilidade por duração e upload de fotos são etapas futuras.

## Variáveis opcionais
- `ADMIN_USER`
- `ADMIN_PASSWORD`
- `SECRET_KEY`
- `DATABASE_PATH`

## Inicialização simplificada no Windows

Dê duplo clique em `INICIAR_CATH_UNHAS.bat`. Na primeira execução, o arquivo cria o ambiente Python e instala Flask (é necessária internet). Depois, abra `http://127.0.0.1:5000`.

Painel: `http://127.0.0.1:5000/login` — usuário inicial `admin`, senha `admin123`. Altere as credenciais antes de publicar na internet.
