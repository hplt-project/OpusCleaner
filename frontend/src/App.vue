<script setup>
import { RouterLink, RouterView } from 'vue-router'
import appLogo from './assets/datailor-logo.svg';
import euLogo from './assets/eu.png';
import horizonLogo from './assets/horizon-europe.png';
</script>

<template>
  <div class="navbar">
    <RouterLink v-bind:to="{name:'list-datasets'}"><img class="logo-datailor" :src="appLogo" alt="Datailor logo"></RouterLink>
  </div>
  <RouterView></RouterView>
  <div class="footer">
    <div class="thanking">
      <img :src="euLogo" alt="EU logo" class="eu-flag">
      <p>
        This project has received funding from the European Union’s Horizon
        Europe research and innovation programme under grant agreement No
        101070350
      </p>
    </div>
    <div class="thanking">
      <img :src="horizonLogo" alt="Horizon Europe logo" class="horizon-flag">
      <p>
        The contents of this publication are the sole responsibility of the
        HPLT consortium and do not necessarily reflect the opinion of the
        European Union.
      </p>
    </div>
    <div class="version">
      <p><a href="https://github.com/hplt-project/OpusCleaner/tree/__OPUS_CLEANER_COMMIT__" title="Commit __OPUS_CLEANER_COMMIT__">Version __OPUS_CLEANER_VERSION__</a></p>
    </div>
  </div>
</template>

<style>
@import 'css/property-list.css';

:root {
  --background-color: #fff;
  --border-color: #17223d;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  margin: 20px 60px;
  font-family: "Lato", sans-serif;
}

.navbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 30px;
  align-items: center;
}

.footer {
  display: flex;
  width: 75%;
  margin: 60px auto;
  font-family: "Lato", sans-serif;
}

.eu-flag,
.horizon-flag {
  width: 50px;
  height: auto;
  margin: 0 10px 0 0;
  flex: 0;
  align-self: flex-start;
}

.thanking {
  display: flex;
}

.version {
  white-space: nowrap;
}

.icon-button {
  appearance: none;
  border: none;
  background: inherit;
  cursor: pointer;
  color: inherit;
}

.icon-button:visited {
  color: inherit;
}

.icon-button:disabled {
  cursor: inherit;
  opacity: 0.5; /* There should be a better way */
}
</style>
