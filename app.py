# app.py

import os
import calendar
from flask import Flask, render_template, request, jsonify
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO (sem alterações) ---
MY_APP_ID = os.environ.get('MY_APP_ID')
MY_APP_SECRET = os.environ.get('MY_APP_SECRET')
MY_ACCESS_TOKEN = os.environ.get('MY_ACCESS_TOKEN')
AD_ACCOUNT_ID_1 = os.environ.get('AD_ACCOUNT_ID_1')
AD_ACCOUNT_ID_2 = os.environ.get('AD_ACCOUNT_ID_2')
AD_ACCOUNT_NAME_1 = 'Bella Serra'
AD_ACCOUNT_NAME_2 = 'Vista Bella'

FacebookAdsApi.init(MY_APP_ID, MY_APP_SECRET, MY_ACCESS_TOKEN)
app = Flask(__name__)

# --- FUNÇÃO DE BUSCA (usada pelas duas rotas) ---
def fetch_insights(account_id, start_date, end_date):
    """
    Função base que faz a chamada à API da Meta para um período.
    """
    try:
        if not account_id:
            return [] # Retorna lista vazia se a conta não estiver configurada

        account = AdAccount(account_id)
        params = {
            'level': 'campaign',
            'time_range': {'since': start_date, 'until': end_date},
            'time_increment': 1,
            'fields': ['campaign_name', 'spend', 'actions'],
            'action_breakdowns': ['action_type'],
        }
        return account.get_insights(params=params)

    except FacebookRequestError as e:
        print(f"Erro na API da Meta para a conta {account_id}: {e}")
        return [] # Retorna lista vazia em caso de erro

# --- ROTA PARA O GRÁFICO INTERATIVO (agora mais simples) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    end_date_str = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date_str = request.args.get('start_date', (datetime.now() - timedelta(days=29)).strftime('%Y-%m-%d'))
    
    # Processa os dados para cada conta
    def process_data(account_id):
        insights = fetch_insights(account_id, start_date_str, end_date_str)
        total_spend = 0
        total_results = 0
        daily_data = []

        # ... (lógica de processamento de insights) ...
        # (Esta parte poderia ser refatorada para uma função helper também, mas vamos manter assim por clareza)
        processed_days = {}
        for insight in insights:
            campaign_name = insight.get('campaign_name', '').lower()
            if 'vaga' in campaign_name or 'vagas' in campaign_name: continue
            date_str = insight['date_start']
            spend = float(insight['spend'])
            results = 0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action['action_type'] == 'onsite_conversion.messaging_conversation_started_7d':
                        results = int(action['value'])
                        break
            if date_str not in processed_days:
                processed_days[date_str] = {'spend': 0.0, 'results': 0}
            processed_days[date_str]['spend'] += spend
            processed_days[date_str]['results'] += results
        
        for date, values in sorted(processed_days.items()):
            total_spend += values['spend']
            total_results += values['results']
            cpl = (values['spend'] / values['results']) if values['results'] > 0 else 0
            daily_data.append({'date': date, 'cpl': round(cpl, 2), 'total_spend': round(values['spend'], 2), 'total_results': values['results']})

        avg_cpl = (total_spend / total_results) if total_results > 0 else 0
        return {'daily_data': daily_data, 'average_cpl': round(avg_cpl, 2)}

    data1 = process_data(AD_ACCOUNT_ID_1)
    data2 = process_data(AD_ACCOUNT_ID_2)
    
    return jsonify({
        'account1': {'name': AD_ACCOUNT_NAME_1, 'stats': data1},
        'account2': {'name': AD_ACCOUNT_NAME_2, 'stats': data2}
    })

# --- ROTA DE DADOS ANUAIS (TOTALMENTE REFEITA E OTIMIZADA) ---
@app.route('/get_yearly_data')
def get_yearly_data():
    current_year = datetime.now().year
    start_of_year = f'{current_year}-01-01'
    end_of_year = f'{current_year}-12-31'
    
    yearly_results = {
        'account1': {'name': AD_ACCOUNT_NAME_1},
        'account2': {'name': AD_ACCOUNT_NAME_2},
    }

    # Processa os dados para cada conta UMA ÚNICA VEZ
    for acc_key, acc_id in [('account1', AD_ACCOUNT_ID_1), ('account2', AD_ACCOUNT_ID_2)]:
        # 1. FAZ A CHAMADA ÚNICA PARA O ANO INTEIRO
        all_insights = fetch_insights(acc_id, start_of_year, end_of_year)
        
        # 2. INICIALIZA ESTRUTURAS PARA GUARDAR OS DADOS PROCESSADOS
        quarter_totals = {q: {'spend': 0, 'results': 0, 'daily_data': []} for q in ['q1', 'q2', 'q3', 'q4']}
        month_totals = {m: {'spend': 0, 'results': 0} for m in range(1, 13)}

        # 3. PROCESSA OS DADOS DO ANO INTEIRO DE UMA VEZ
        for insight in all_insights:
            campaign_name = insight.get('campaign_name', '').lower()
            if 'vaga' in campaign_name or 'vagas' in campaign_name:
                continue
            
            day_date = datetime.strptime(insight['date_start'], '%Y-%m-%d')
            spend = float(insight['spend'])
            results = 0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action['action_type'] == 'onsite_conversion.messaging_conversation_started_7d':
                        results = int(action['value']); break
            
            # Reparte os dados por mês
            month_totals[day_date.month]['spend'] += spend
            month_totals[day_date.month]['results'] += results
            
            # Reparte os dados por trimestre
            quarter = f'q{(day_date.month - 1) // 3 + 1}'
            quarter_totals[quarter]['spend'] += spend
            quarter_totals[quarter]['results'] += results
            cpl = (spend / results) if results > 0 else 0
            quarter_totals[quarter]['daily_data'].append({
                'date': insight['date_start'], 'cpl': round(cpl, 2), 
                'total_spend': round(spend, 2), 'total_results': results
            })
            
        # 4. CALCULA AS MÉDIAS FINAIS
        final_quarterly_data = {}
        for q, totals in quarter_totals.items():
            avg_cpl = (totals['spend'] / totals['results']) if totals['results'] > 0 else 'N/D'
            if isinstance(avg_cpl, float): avg_cpl = round(avg_cpl, 2)
            final_quarterly_data[q] = {'daily_data': totals['daily_data'], 'average_cpl': avg_cpl}
            
        final_monthly_averages = {}
        months_pt = {i: calendar.month_name[i] for i in range(1, 13)}
        for m, totals in month_totals.items():
            month_name_pt = months_pt[m]
            avg_cpl = (totals['spend'] / totals['results']) if totals['results'] > 0 else 'N/D'
            if isinstance(avg_cpl, float): avg_cpl = round(avg_cpl, 2)
            final_monthly_averages[month_name_pt] = avg_cpl
            
        yearly_results[acc_key]['quarterly_data'] = final_quarterly_data
        yearly_results[acc_key]['monthly_averages'] = final_monthly_averages
        
    return jsonify(yearly_results)

# --- INICIA O SERVIDOR ---
if __name__ == '__main__':
    app.run(debug=True)