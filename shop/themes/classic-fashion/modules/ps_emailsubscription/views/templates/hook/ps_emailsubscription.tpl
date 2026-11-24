{**
 * Child Theme classic-fashion - Dzielony newsletter ze zdjeciem 10% rabatu (mosquito-sklep.pl)
 *}
<div class="block_newsletter msq-newsletter-split col-12" id="blockEmailSubscription_{$hookName}">
  <div class="msq-newsletter-grid">
    <div class="msq-newsletter-form">
      <h2 id="block-newsletter-label" class="msq-newsletter-title">Zapisz się do newslettera</h2>
      <p class="msq-newsletter-lead">Bądź na bieżąco z premierami nowych kolekcji szytych w Polsce oraz promocjami.</p>
      <form action="{$urls.current_url}#blockEmailSubscription_{$hookName}" method="post">
        <div class="msq-newsletter-controls">
          <div class="input-wrapper">
            <input
              name="email"
              type="email"
              value="{$value}"
              placeholder="Wpisz swój adres e-mail"
              aria-labelledby="block-newsletter-label"
              required
            >
          </div>
          <button
            class="btn btn-primary msq-newsletter-submit"
            name="submitNewsletter"
            type="submit"
          >
            Zapisz się
          </button>
        </div>
        <input type="hidden" name="blockHookName" value="{$hookName}" />
        <input type="hidden" name="action" value="0">
        {if $conditions}
          <p class="msq-newsletter-terms">{$conditions}</p>
        {/if}
        {if $msg}
          <p class="alert {if $nw_error}alert-danger{else}alert-success{/if}">
            {$msg}
          </p>
        {/if}
        {hook h='displayNewsletterRegistration'}
        {if isset($id_module)}
          {hook h='displayGDPRConsent' id_module=$id_module}
        {/if}
      </form>
    </div>

    <div class="msq-newsletter-visual hidden-sm-down">
      <figure class="msq-newsletter-figure">
        <img src="{$urls.base_url}themes/classic-fashion/assets/img/banner-fashion.jpg" alt="Kolekcja Mosquito – rabat powitalny" width="700" height="280" loading="lazy">
        <figcaption class="msq-newsletter-badge">
          <strong>10%</strong>
          <span>rabatu na pierwsze zakupy</span>
        </figcaption>
      </figure>
    </div>
  </div>
</div>
