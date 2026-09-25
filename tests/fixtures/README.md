# Fixtures de teste

`carolina_diet.json` é uma cópia de `tests/diet_plan_parsed.json` (saída real
do `WebDietParser` para o PDF de exemplo), com uma limpeza pontual: foram
removidos itens de refeição com `unit == "Kcal"`.

Esses itens são um artefato conhecido do parser (`scrap_do_pdf.py`): em
algumas refeições, uma linha de resumo nutricional (nome da refeição +
macros + calorias) é capturada como se fosse um `FoodItem` dentro da
refeição seguinte (ex.: `"Janta 2-Virado de ovo 22.1g 16.5g 55.0g"` com
`unit: "Kcal"`, dentro da refeição "Ceia"). Isso não é um alimento comprável
e não faz parte do escopo desta etapa (o parser é tratado como dependência
externa já existente). O fixture foi limpo para não distorcer os testes do
núcleo de compras, mas o problema deve ser corrigido no parser
(`scrap_do_pdf.py`) em uma iteração futura.
