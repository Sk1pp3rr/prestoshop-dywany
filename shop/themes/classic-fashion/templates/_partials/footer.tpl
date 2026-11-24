{**
 * Child Theme classic-fashion - Dol strony (Media o nas, Dlaczego Mosquito?, stopka i linki W2)
 *}
<div class="container">
  <div class="row">
    {block name='hook_footer_before'}
      {hook h='displayFooterBefore'}
    {/block}
  </div>

  <section class="msq-media-strip" aria-label="Media o nas">
    <h2 class="msq-media-strip__title">Media o nas</h2>
    <div class="msq-media-strip__logos">
      <span class="msq-media-logo msq-media-logo--serif">GLAMOUR</span>
      <span class="msq-media-logo msq-media-logo--serif">VOGUE</span>
      <span class="msq-media-logo msq-media-logo--serif">Forbes</span>
      <span class="msq-media-logo msq-media-logo--serif">ELLE</span>
      <span class="msq-media-logo">onet</span>
      <span class="msq-media-logo">WP</span>
    </div>
  </section>
</div>

<div class="footer-container">
  <div class="container">
    <section class="msq-why-boxes" aria-label="Dlaczego Mosquito">
      <h2 class="msq-why-boxes__title">Dlaczego Mosquito?</h2>
      <div class="msq-why-boxes__grid">
        <div class="msq-why-box">
          <span class="msq-why-box__icon" aria-hidden="true">&#x2605;</span>
          <div>
            <h3>Co miesiąc nowe produkty</h3>
            <p>U nas zawsze znajdziesz coś wyjątkowego w nowej kolekcji.</p>
          </div>
        </div>
        <div class="msq-why-box">
          <span class="msq-why-box__icon" aria-hidden="true">&#x2702;</span>
          <div>
            <h3>Szyte w Polsce</h3>
            <p>Jesteśmy polską marką i szyjemy nasze modele w polskich szwalniach.</p>
          </div>
        </div>
        <div class="msq-why-box">
          <span class="msq-why-box__icon" aria-hidden="true">&#x2713;</span>
          <div>
            <h3>Darmowa dostawa</h3>
            <p>Bezpłatna wysyłka InPost (25 kg) i DPD (31.5 kg) od 2000 zł (limit 50 kg).</p>
          </div>
        </div>
        <div class="msq-why-box">
          <span class="msq-why-box__icon" aria-hidden="true">&#x21BA;</span>
          <div>
            <h3>14 dni na zwrot</h3>
            <p>Przelew tradycyjny lub płatność za pobraniem DPD z fakturą VAT PDF.</p>
          </div>
        </div>
      </div>
    </section>

    <div class="row">
      {block name='hook_footer'}
        {hook h='displayFooter'}
      {/block}
    </div>
    <div class="row">
      {block name='hook_footer_after'}
        {hook h='displayFooterAfter'}
      {/block}
    </div>
    <div class="row">
      <div class="col-md-12">
        <div class="msq-footer-cms-bar">
          <a href="{url entity='cms' id=4}">O sklepie</a>
          <a href="{url entity='cms' id=3}">Regulamin</a>
          <a href="{url entity='cms' id=2}">Polityka prywatności</a>
          <a href="{url entity='cms' id=1}">Dostawa</a>
          <a href="{url entity='cms' id=5}">Formy płatności</a>
        </div>
        <p class="text-sm-center msq-copyright">
          {block name='copyright_link'}
            &copy; {'Y'|date} MOSQUITO &ndash; Wszelkie prawa zastrzeżone
          {/block}
        </p>
      </div>
    </div>
  </div>
</div>
