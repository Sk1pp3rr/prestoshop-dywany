{**
 * Child Theme classic-fashion - Nowosci w asymetrycznym ukladzie mosquito-sklep.pl
 * Pierwsze 2 produkty obok drugiego banera, kolejne 4 w rzedzie 4-kolumnowym pod spodem.
 *}
{if !empty($products)}
<section class="featured-products msq-split-section msq-new-section" aria-label="{l s='New products' d='Shop.Theme.Catalog'}">
  <h2 class="sr-only">{l s='New products' d='Shop.Theme.Catalog'}</h2>
  <div class="products msq-split-pair">
    {foreach from=$products item="product" key="idx"}
      {if $idx < 2}
        {include file="catalog/_partials/miniatures/product.tpl" product=$product}
      {/if}
    {/foreach}
  </div>
  <div class="products msq-quad-row">
    {foreach from=$products item="product" key="idx"}
      {if $idx >= 2 && $idx < 6}
        {include file="catalog/_partials/miniatures/product.tpl" product=$product}
      {/if}
    {/foreach}
  </div>
</section>
{/if}
