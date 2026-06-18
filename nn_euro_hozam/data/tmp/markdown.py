
legend = '<div style="display: flex; gap: 18px; align-items: center; margin-bottom: 6px;">{0}</div>'
legend_div = '<div><span style="display:inline-block; width:12px; height:3px; background:#2962FF; margin-right:6px;"></span>{0}</div>'
titles = ['CPU', 'Mem', "Disk"]
legend_divs = ''.join(legend_div.format(title) for title in titles)
print(legend.format(legend_divs))
