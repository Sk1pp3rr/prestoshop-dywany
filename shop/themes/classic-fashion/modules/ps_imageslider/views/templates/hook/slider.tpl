{**
 * Child Theme classic-fashion - Pionowy lewy Hero Banner w ukladzie mosquito-sklep.pl
 *}
{if $homeslider.slides}
  <div id="carousel" data-ride="carousel" class="carousel slide msq-hero-carousel" data-interval="9000" data-wrap="{(string)$homeslider.wrap}" data-pause="{$homeslider.pause}" data-touch="true" aria-roledescription="carousel" aria-label="Kolekcje Mosquito">
    <ol class="carousel-indicators">
      {foreach from=$homeslider.slides item=slide key=idxSlide name='homeslider'}
      <li data-target="#carousel" data-slide-to="{$idxSlide}"{if $idxSlide == 0} class="active"{/if}></li>
      {/foreach}
    </ol>
    <ul class="carousel-inner">
      {foreach from=$homeslider.slides item=slide name='homeslider'}
        <li class="carousel-item {if $smarty.foreach.homeslider.first}active{/if}">
          {if !empty($slide.url)}<a href="{$slide.url}" class="msq-hero-link">{/if}
            <figure class="msq-hero-figure">
              <img src="{$slide.image_url}" alt="{$slide.legend|escape}"{if $smarty.foreach.homeslider.first} fetchpriority="high"{else} loading="lazy"{/if} width="640" height="860">
              {if $slide.title || $slide.description}
                <figcaption class="caption msq-hero-caption">
                  <h2 class="display-1 text-uppercase">{$slide.title}</h2>
                  <div class="caption-description">{$slide.description nofilter}</div>
                </figcaption>
              {/if}
            </figure>
          {if !empty($slide.url)}</a>{/if}
        </li>
      {/foreach}
    </ul>
    <div class="direction">
      <a class="left carousel-control" href="#carousel" role="button" data-slide="prev" aria-label="{l s='Previous' d='Shop.Theme.Global'}">
        <span class="icon-prev" aria-hidden="true">
          <i class="material-icons">&#xE5CB;</i>
        </span>
      </a>
      <a class="right carousel-control" href="#carousel" role="button" data-slide="next" aria-label="{l s='Next' d='Shop.Theme.Global'}">
        <span class="icon-next" aria-hidden="true">
          <i class="material-icons">&#xE5CC;</i>
        </span>
      </a>
    </div>
  </div>
{/if}
