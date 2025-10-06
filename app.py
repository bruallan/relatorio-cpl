# app.py

import os
import calendar
from flask import Flask, render_template, request, jsonify
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError
from datetime import datetime, timedelta


# Substitua com suas informações reais. Mantenha isso seguro!
MY_APP_ID = os.environ.get('MY_APP_ID')
MY_APP_SECRET = os.environ.get('MY_APP_SECRET')
MY_ACCESS_TOKEN = os.environ.get('MY_ACCESS_TOKEN')

# IDs das suas duas contas de anúncio
AD_ACCOUNT_ID_1 = os.environ.get('AD_ACCOUNT_ID_1')
AD_ACCOUNT_ID_2 = os.environ.get('AD_ACCOUNT_ID_2')

# Nomes para exibição no gráfico
AD_ACCOUNT_NAME_1 = 'Bella Serra'
AD_ACCOUNT_NAME_2 = 'Vista Bella'

FacebookAdsApi.init(MY_APP_ID, MY_APP_SECRET, MY_ACCESS_TOKEN)

app = Flask(__name__)

# --- FUNÇÃO PRINCIPAL PARA BUSCAR DADOS (MODIFICADA) ---
def fetch_account_data(account_id, start_date, end_date):
    """
    Busca dados diários e calcula a média de CPL para o período total.
    """
    try:
        account = AdAccount(account_id)
        
        params = {
            'level': 'campaign',
            'time_range': {'since': start_date, 'until': end_date},
            'time_increment': 1,
            'fields': ['campaign_name', 'spend', 'actions'],
            'action_breakdowns': ['action_type'],
        }

        insights = account.get_insights(params=params)
        
        daily_data = {}
        total_period_spend = 0.0
        total_period_results = 0

        for insight in insights:
            campaign_name = insight.get('campaign_name', '').lower()
            
            if 'vaga' in campaign_name or 'vagas' in campaign_name:
                continue

            date_str = insight['date_start']
            spend = float(insight['spend'])
            
            results = 0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action['action_type'] == 'onsite_conversion.messaging_conversation_started_7d':
                        results = int(action['value'])
                        break
            
            if date_str not in daily_data:
                daily_data[date_str] = {'spend': 0.0, 'results': 0}
            
            daily_data[date_str]['spend'] += spend
            daily_data[date_str]['results'] += results
        
        # Formata os dados diários e calcula os totais do período
        formatted_data = []
        for date, values in sorted(daily_data.items()):
            cost_per_lead = (values['spend'] / values['results']) if values['results'] > 0 else 0
            formatted_data.append({
                'date': date,
                'cpl': round(cost_per_lead, 2),
                'total_spend': round(values['spend'], 2),
                'total_results': values['results']
            })
            # Soma aos totais do período
            total_period_spend += values['spend']
            total_period_results += values['results']

        # **NOVO: Calcula o CPL médio do período**
        average_cpl = (total_period_spend / total_period_results) if total_period_results > 0 else 0
        
        # **NOVO: Retorna um dicionário com os dados diários E a média**
        return {
            'daily_data': formatted_data,
            'average_cpl': round(average_cpl, 2)
        }

    except FacebookRequestError as e:
        print(f"Erro ao buscar dados para a conta {account_id}: {e}")
        return {'error': str(e)}

# --- ROTAS DA APLICAÇÃO ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    end_date_str = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date_str = request.args.get(
        'start_date', 
        (datetime.now() - timedelta(days=29)).strftime('%Y-%m-%d')
    )
    
    data1 = fetch_account_data(AD_ACCOUNT_ID_1, start_date_str, end_date_str)
    data2 = fetch_account_data(AD_ACCOUNT_ID_2, start_date_str, end_date_str)
    
    # A resposta JSON agora conterá a estrutura retornada pela função
    return jsonify({
        'account1': {'name': AD_ACCOUNT_NAME_1, 'stats': data1},
        'account2': {'name': AD_ACCOUNT_NAME_2, 'stats': data2}
    })

# --- NOVA ROTA PARA BUSCAR OS DADOS ANUAIS ---
@app.route('/get_yearly_data')
def get_yearly_data():
    """
    Busca todos os dados do ano corrente, já separados por trimestre e mês.
    """
    current_year = datetime.now().year
    
    # Define os períodos
    quarters = {
        'q1': (f'{current_year}-01-01', f'{current_year}-03-31'),
        'q2': (f'{current_year}-04-01', f'{current_year}-06-30'),
        'q3': (f'{current_year}-07-01', f'{current_year}-09-30'),
        'q4': (f'{current_year}-10-01', f'{current_year}-12-31'),
    }
    
    months = {
        i: (f'{current_year}-{i:02d}-01', f'{current_year}-{i:02d}-{calendar.monthrange(current_year, i)[1]}')
        for i in range(1, 13)
    }

    # Estrutura para guardar os resultados
    yearly_results = {
        'account1': {'name': AD_ACCOUNT_NAME_1, 'quarterly_data': {}, 'monthly_averages': {}},
        'account2': {'name': AD_ACCOUNT_NAME_2, 'quarterly_data': {}, 'monthly_averages': {}},
    }

    # Busca os dados para cada conta
    for acc_key, acc_id in [('account1', AD_ACCOUNT_ID_1), ('account2', AD_ACCOUNT_ID_2)]:
        # Busca dados trimestrais
        for q_key, (start, end) in quarters.items():
            if datetime.strptime(start, '%Y-%m-%d') > datetime.now():
                yearly_results[acc_key]['quarterly_data'][q_key] = {'daily_data': [], 'average_cpl': 'N/D'}
            else:
                yearly_results[acc_key]['quarterly_data'][q_key] = fetch_account_data(acc_id, start, end)

        # Busca dados mensais
        for m_key, (start, end) in months.items():
            month_name = calendar.month_name[m_key]
            if datetime.strptime(start, '%Y-%m-%d') > datetime.now():
                yearly_results[acc_key]['monthly_averages'][month_name] = 'N/D'
            else:
                month_data = fetch_account_data(acc_id, start, end)
                yearly_results[acc_key]['monthly_averages'][month_name] = month_data['average_cpl']

    return jsonify(yearly_results)

# --- INICIA O SERVIDOR ---
if __name__ == '__main__':
    app.run(debug=True)