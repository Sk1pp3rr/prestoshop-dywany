{**
 * Child Theme classic-fashion - Sekcja Promocje na stronie glownej (D1 + D3)
 * Dopasowana do siatki 12-kolumnowej .msq-home-canvas i hierarchii naglowkow h2 (Lighthouse Accessibility).
 *}
{if !empty($products)}
<section class="featured-products msq-specials-section" aria-label="Promocje">
  <div class="msq-section-head">
    <h2 class="msq-section-title">Promocje</h2>
    <a class="msq-section-link" href="{$allSpecialProductsLink}">Wszystkie promocje &rsaquo;</a>
  </div>
  <div class="products msq-quad-row">
    {foreach from=$products item="product" key="idx"}
      {if $idx < 4}
        {include file="catalog/_partials/miniatures/product.tpl" product=$product}
      {/if}
    {/foreach}
  </div>
</section>
{/if}
