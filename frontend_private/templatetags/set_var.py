from typing import Any

from django import template

register = template.Library()


class SetVarNode(template.Node):
    def __init__(self, var_name: str, var_value: Any) -> None:
        self.var_name = var_name
        self.var_value = var_value

    def render(self, context: template.Context) -> str:
        super().render(context)
        try:
            value = template.Variable(self.var_value).resolve(context)
        except template.VariableDoesNotExist:
            value = ""
        context[self.var_name] = value
        return ""


@register.tag("set")
def set_var(parser: template.base.Parser, token: template.base.Token) -> SetVarNode:
    """
    {% set <var_name>  = <var_value> %}
    """
    parts = token.split_contents()
    if len(parts) < 4:  # noqa: PLR2004
        raise template.TemplateSyntaxError(
            "'set' tag must be of the form:  {% set <var_name>  = <var_value> %}"
        )
    return SetVarNode(parts[1], parts[3])
