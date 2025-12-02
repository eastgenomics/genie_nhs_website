document.addEventListener('DOMContentLoaded', function () {
    // Process INFO tooltips that are displayed/hidden on click.
    // "tooltip-click" is an artificial class added to flag elements
    // with such tooltips.
    const infos = document.querySelectorAll('.tooltip-click');

    infos.forEach(info => {
        const tooltip = new bootstrap.Tooltip(info, {
            trigger: 'manual',
            container: 'body'
        });

        // Store visibility state directly on the element
        info._tooltipVisible = false;

        // Toggle tooltip on info click
        info.addEventListener('click', function (e) {
            e.stopPropagation(); // prevent closing immediately
            if (info._tooltipVisible) {
                tooltip.hide();
            } else {
                tooltip.show();
            }
            info._tooltipVisible = !info._tooltipVisible;
        });
    });

    // Hide all info tooltips if clicking anywhere else
    document.addEventListener('click', function (e) {
        infos.forEach(info => {
            if (!info.contains(e.target)) {
                const instance = bootstrap.Tooltip.getInstance(info);
                if (instance) instance.hide();
                info._tooltipVisible = false;
            }
        });
    });
});