"""Django template tags for live components."""

from django import template
from django.utils.safestring import mark_safe

from ..core import StateSerializer, registry

register = template.Library()


@register.simple_tag(takes_context=True)
def live_component(context, name, **params):
    """
    Render a live component.

    Usage:
        {% load components %}
        {% live_component "counter" initial=5 %}
        {% live_component "order_form" pk=order.id %}
    """
    # Get component class
    component_cls = registry.get(name)
    if not component_cls:
        return f"<!-- Component '{name}' not found -->"

    # Create component
    component = component_cls(**params)

    # Dispatch (initial render)
    result = component.dispatch()

    # Return HTML
    return mark_safe(result["html"])


@register.simple_tag
def component_state(state_dict):
    """
    Serialize component state for HTMX attributes.

    Usage:
        hx-vals='{"state": "{% component_state state %}"}'
    """
    return StateSerializer.serialize(state_dict)


@register.inclusion_tag("components/htmx_component.html", takes_context=True)
def htmx_component(context, name, **params):
    """
    Render component with HTMX wrapper.

    Usage:
        {% htmx_component "counter" initial=5 %}

    Requires template: components/htmx_component.html
    """
    component_cls = registry.get(name)
    if not component_cls:
        return {"error": f"Component '{name}' not found"}

    component = component_cls(**params)
    result = component.dispatch()

    return {
        "name": name,
        "html": mark_safe(result["html"]),
        "state": result["state"],
        "component_id": result["component_id"],
    }


@register.filter
def component_errors(errors_dict, field_name):
    """
    Get field errors from component error dict.

    Usage:
        {% if errors|component_errors:"email" %}
            {{ errors|component_errors:"email"|first }}
        {% endif %}
    """
    if isinstance(errors_dict, dict):
        return errors_dict.get(field_name, [])
    return []


@register.simple_tag
def component_js(component_id):
    """
    Generate JavaScript for component WebSocket connection.

    Usage:
        {% component_js component.id %}
    """
    js = f"""
    <script>
    (function() {{
        const componentId = '{component_id}';
        const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
        const ws = new WebSocket(proto + location.host + '/ws/');

        ws.onopen = function() {{
            // Subscribe to component updates
            ws.send(JSON.stringify({{
                type: 'subscribe',
                component_id: componentId
            }}));
        }};

        ws.onmessage = function(event) {{
            const data = JSON.parse(event.data);

            if (data.type === 'component_update' && data.component_id === componentId) {{
                // Update component HTML
                const element = document.getElementById(componentId);
                if (element) {{
                    element.outerHTML = data.html;
                }}
            }}
        }};

        ws.onerror = function(error) {{
            console.error('WebSocket error:', error);
        }};

        ws.onclose = function() {{
            console.log('WebSocket closed');
        }};
    }})();
    </script>
    """
    return mark_safe(js)


# Django-Cotton specific tags
@register.simple_tag(takes_context=True)
def cotton_component(context, name, **attrs):
    """
    Render a live component as a Cotton component.

    Usage:
        {% load components %}
        {% cotton_component "counter" initial=5 class="my-counter" %}

    This renders the component and wraps it in a Cotton-compatible structure.
    """
    component_cls = registry.get(name)
    if not component_cls:
        return f"<!-- Component '{name}' not found -->"

    # Create component
    component = component_cls(**attrs)

    # Dispatch
    result = component.dispatch()

    # For Cotton integration, we can pass props to Cotton components
    # or just render the component directly
    return mark_safe(result["html"])


@register.simple_tag
def component_attrs(component_id, state_dict, **extra_attrs):
    """
    Generate HTMX attributes for component interaction.

    Usage:
        <button {% component_attrs component.id state %}>Click</button>
    """
    attrs = {
        "hx-target": f"#{component_id}",
        "hx-swap": "outerHTML",
    }

    # Add extra attributes
    attrs.update(extra_attrs)

    # Build attribute string
    attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return mark_safe(attr_str)
