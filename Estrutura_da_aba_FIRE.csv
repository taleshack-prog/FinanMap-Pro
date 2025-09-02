function atualizarPrecosAlphaVantage() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const config = ss.getSheetByName("config");
  const dadosSheet = ss.getSheetByName("dados_ativos");
  const apiKey = "NCRVLI6PW7KHO7FA";
  dadosSheet.clearContents().appendRow(["Data", "Ativo", "Preço (fechamento)"]);

  const ativos = config.getRange("A2:A").getValues().flat().filter(a => a);
  const dataInicio = new Date(config.getRange("B2").getValue());
  const dataFim = new Date(config.getRange("C2").getValue());

  ativos.forEach(ticker => {
    const url = `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=${ticker}&apikey=${apiKey}`;
    try {
      const response = UrlFetchApp.fetch(url);
      const json = JSON.parse(response.getContentText());
      const series = json["Time Series (Daily)"];

      if (!series) {
        console.log(`❌ Dados indisponíveis ou erro para: ${ticker}`);
        console.log(`📄 Resposta bruta para ${ticker}:`, JSON.stringify(json));
        return;
      }

      const rows = Object.entries(series)
        .filter(([dateStr, _]) => {
          const date = new Date(dateStr);
          return date >= dataInicio && date <= dataFim;
        })
        .map(([dateStr, value]) => [dateStr, ticker, parseFloat(value["4. close"])]);

      rows.forEach(row => dadosSheet.appendRow(row));
      Utilities.sleep(15000); // Aguarda 15s para evitar limite da API
    } catch (e) {
      console.error(`Erro ao buscar dados para ${ticker}:`, e);
    }
  });
}
