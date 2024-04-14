{%- if filter_value and not key -%}
	and (
	{% for field in filter_fields %}
		upper({{ field }}) like upper(:filter_value) {% if not loop.last %}or{% endif %}
	{% endfor %}
	)
{%- endif -%}
